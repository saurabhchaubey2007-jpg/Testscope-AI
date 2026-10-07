import functools

from langgraph.graph import StateGraph, END
from packages.agent_core.state import TestScopeState
from apps.api.app.services.repository_analyzer import analyze_repository
from apps.api.app.services.test_planner import create_test_plan
from apps.api.app.services.test_generator import generate_tests
from apps.api.app.services.test_executor import run_pytest
from apps.api.app.services.failure_analyzer import analyze_failures
from apps.api.app.services.test_repairer import repair_tests
from apps.api.app.services.e2e_generator import (
    create_e2e_plan, generate_e2e_tests, e2e_artifacts_dir, playwright_args,
)
from apps.api.app.services.run_events import record_event, is_cancelled, RunCancelled

MAX_REPAIR_ATTEMPTS = 3
E2E_TIMEOUT_SECONDS = 120


def tracked(step_name: str):
    """Record step start/finish events for live progress and honour cancellation."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(state: TestScopeState):
            run_id = state.get("run_id")
            if run_id and is_cancelled(run_id):
                raise RunCancelled()
            if run_id:
                record_event(run_id, "step_started", step_name)
            result = fn(state)
            if run_id:
                record_event(run_id, "step_finished", step_name)
            return result
        return wrapper
    return decorator


# ---------- helpers ----------

def _phase_tests(state: TestScopeState) -> list:
    phase = state.get("phase", "unit")
    return [t for t in state.get("generated_tests", []) if t.get("test_type", "unit") == phase]


def _run_phase_tests(state: TestScopeState, tests: list) -> dict:
    if state.get("phase") == "e2e":
        return run_pytest(
            tests,
            state["repository_path"],
            extra_args=playwright_args(state["app_url"]),
            artifacts_dir=e2e_artifacts_dir(state["run_id"]),
            timeout=E2E_TIMEOUT_SECONDS,
        )
    return run_pytest(tests, state["repository_path"])


# ---------- unit test nodes ----------

@tracked("analyze_repository")
def node_analyze_repository(state: TestScopeState):
    summary = analyze_repository(state["repository_path"])
    return {"codebase_summary": summary}

@tracked("create_test_plan")
def node_create_test_plan(state: TestScopeState):
    plan = create_test_plan(state["codebase_summary"])
    return {"test_plan": plan, "phase": "unit", "repair_attempts": 0}

@tracked("generate_tests")
def node_generate_tests(state: TestScopeState):
    tests = generate_tests(state["test_plan"], state["repository_path"], state["run_id"], state["codebase_summary"])
    return {"generated_tests": state.get("generated_tests", []) + tests}

@tracked("run_tests")
def node_run_tests(state: TestScopeState):
    results = _run_phase_tests(state, _phase_tests(state))
    merged = dict(state.get("execution_results", {}))
    merged.update(results)
    return {"execution_results": merged}

@tracked("analyze_failures")
def node_analyze_failures(state: TestScopeState):
    phase = state.get("phase", "unit")
    phase_tests = _phase_tests(state)
    phase_names = {t["name"] for t in phase_tests}
    phase_results = {k: v for k, v in state.get("execution_results", {}).items() if k in phase_names}

    new_failures = analyze_failures(phase_results, phase_tests)
    for f in new_failures:
        f["test_type"] = phase
    # Keep failures from other phases untouched
    other = [f for f in state.get("failures", []) if f.get("test_type", "unit") != phase]
    return {"failures": other + new_failures}

@tracked("repair_tests")
def node_repair_tests(state: TestScopeState):
    phase = state.get("phase", "unit")
    phase_failures = [f for f in state.get("failures", []) if f.get("test_type", "unit") == phase]
    attempt = state.get("repair_attempts", 0) + 1
    repairs = repair_tests(phase_failures, state["execution_results"], state["generated_tests"], state["codebase_summary"])
    for r in repairs:
        r["attempt_number"] = attempt
        r["test_type"] = phase
    return {
        # Always advance the counter so a failing repair can't loop forever
        "repair_attempts": attempt,
        "repairs": state.get("repairs", []) + repairs,
    }

@tracked("run_tests_again")
def node_run_tests_again(state: TestScopeState):
    repaired_names = {r["test_name"] for r in state.get("repairs", [])
                      if r.get("attempt_number") == state.get("repair_attempts")
                      and r.get("test_type", "unit") == state.get("phase", "unit")}
    tests = [t for t in _phase_tests(state) if t["name"] in repaired_names] or _phase_tests(state)
    results = _run_phase_tests(state, tests)
    new_results = dict(state["execution_results"])
    new_results.update(results)
    return {"execution_results": new_results}


# ---------- e2e nodes ----------

@tracked("create_e2e_plan")
def node_create_e2e_plan(state: TestScopeState):
    plan = create_e2e_plan(state.get("codebase_summary", {}), state["app_url"])
    return {"e2e_plan": plan, "phase": "e2e", "repair_attempts": 0}

@tracked("generate_e2e_tests")
def node_generate_e2e_tests(state: TestScopeState):
    tests = generate_e2e_tests(state["e2e_plan"], state["app_url"], state["run_id"])
    return {"generated_tests": state.get("generated_tests", []) + tests}


# ---------- report ----------

@tracked("create_report")
def node_create_report(state: TestScopeState):
    results = state.get("execution_results", {})
    report = {
        "run_id": state["run_id"],
        "summary": {
            "generated": len(state.get("generated_tests", [])),
            "passed": sum(1 for r in results.values() if r["status"] == "PASSED"),
            "failed": sum(1 for r in results.values() if r["status"] != "PASSED"),
        },
        "tests": [{"name": k, "status": v["status"]} for k, v in results.items()],
        "failures": state.get("failures", []),
        "repair_attempts": len(state.get("repairs", [])),
    }
    return {"final_report": report}


# ---------- routing ----------

def _wants(state: TestScopeState, test_type: str) -> bool:
    return test_type in (state.get("test_types") or ["unit"])

def route_after_analysis(state: TestScopeState):
    if _wants(state, "unit"):
        return "create_test_plan"
    if _wants(state, "e2e") and state.get("app_url"):
        return "create_e2e_plan"
    return "create_report"

def should_repair(state: TestScopeState):
    phase = state.get("phase", "unit")
    attempts = state.get("repair_attempts", 0)
    has_test_defects = any(
        f["category"] == "TEST_DEFECT" and f.get("test_type", "unit") == phase
        for f in state.get("failures", [])
    )

    if attempts < MAX_REPAIR_ATTEMPTS and has_test_defects:
        return "repair_tests"
    if phase == "unit" and _wants(state, "e2e") and state.get("app_url"):
        return "create_e2e_plan"
    return "create_report"


def build_graph():
    workflow = StateGraph(TestScopeState)
    
    workflow.add_node("analyze_repository", node_analyze_repository)
    workflow.add_node("create_test_plan", node_create_test_plan)
    workflow.add_node("generate_tests", node_generate_tests)
    workflow.add_node("run_tests", node_run_tests)
    workflow.add_node("analyze_failures", node_analyze_failures)
    workflow.add_node("repair_tests", node_repair_tests)
    workflow.add_node("run_tests_again", node_run_tests_again)
    workflow.add_node("create_e2e_plan", node_create_e2e_plan)
    workflow.add_node("generate_e2e_tests", node_generate_e2e_tests)
    workflow.add_node("run_e2e_tests", node_run_tests)
    workflow.add_node("create_report", node_create_report)
    
    workflow.set_entry_point("analyze_repository")

    workflow.add_conditional_edges("analyze_repository", route_after_analysis, {
        "create_test_plan": "create_test_plan",
        "create_e2e_plan": "create_e2e_plan",
        "create_report": "create_report",
    })
    
    # Unit phase
    workflow.add_edge("create_test_plan", "generate_tests")
    workflow.add_edge("generate_tests", "run_tests")
    workflow.add_edge("run_tests", "analyze_failures")

    # E2E phase (shares the analyze/repair loop)
    workflow.add_edge("create_e2e_plan", "generate_e2e_tests")
    workflow.add_edge("generate_e2e_tests", "run_e2e_tests")
    workflow.add_edge("run_e2e_tests", "analyze_failures")
    
    workflow.add_conditional_edges("analyze_failures", should_repair, {
        "repair_tests": "repair_tests",
        "create_e2e_plan": "create_e2e_plan",
        "create_report": "create_report"
    })
    
    workflow.add_edge("repair_tests", "run_tests_again")
    workflow.add_edge("run_tests_again", "analyze_failures") # Loop back to check if it worked
    
    workflow.add_edge("create_report", END)
    
    return workflow.compile()

app = build_graph()

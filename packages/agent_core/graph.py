from langgraph.graph import StateGraph, END
from packages.agent_core.state import TestScopeState
from apps.api.app.services.repository_analyzer import analyze_repository
from apps.api.app.services.test_planner import create_test_plan
from apps.api.app.services.test_generator import generate_tests
from apps.api.app.services.test_executor import run_pytest
from apps.api.app.services.failure_analyzer import analyze_failures
from apps.api.app.services.test_repairer import repair_tests

# Define node functions
def node_analyze_repository(state: TestScopeState):
    summary = analyze_repository(state["repository_path"])
    return {"codebase_summary": summary}

def node_create_test_plan(state: TestScopeState):
    plan = create_test_plan(state["codebase_summary"])
    return {"test_plan": plan}

def node_generate_tests(state: TestScopeState):
    tests = generate_tests(state["test_plan"], state["repository_path"], state["run_id"])
    return {"generated_tests": tests}

def node_run_tests(state: TestScopeState):
    results = run_pytest(state["generated_tests"], state["repository_path"])
    return {"execution_results": results}

def node_analyze_failures(state: TestScopeState):
    failures = analyze_failures(state["execution_results"], state["generated_tests"])
    return {"failures": failures}

def node_repair_tests(state: TestScopeState):
    repairs = repair_tests(state["failures"], state["execution_results"], state["generated_tests"], state["codebase_summary"])
    # If we made repairs, increment attempt counter
    if repairs:
        return {"repair_attempts": state.get("repair_attempts", 0) + 1}
    return {}

def node_run_tests_again(state: TestScopeState):
    results = run_pytest(state["generated_tests"], state["repository_path"])
    # Update results with new runs
    new_results = state["execution_results"].copy()
    new_results.update(results)
    return {"execution_results": new_results}

def node_create_report(state: TestScopeState):
    # This will be handled properly in report_service, we just format basic dict here
    report = {
        "run_id": state["run_id"],
        "summary": {
            "generated": len(state["generated_tests"]),
            "passed": sum(1 for r in state["execution_results"].values() if r["status"] == "PASSED"),
            "failed": sum(1 for r in state["execution_results"].values() if r["status"] == "FAILED"),
        },
        "tests": [{"name": k, "status": v["status"]} for k, v in state["execution_results"].items()],
        "failures": state.get("failures", []),
        "repair_attempts": state.get("repair_attempts", 0)
    }
    return {"final_report": report}

def should_repair(state: TestScopeState):
    attempts = state.get("repair_attempts", 0)
    has_test_defects = any(f["category"] == "TEST_DEFECT" for f in state.get("failures", []))
    
    if attempts < 3 and has_test_defects:
        return "repair_tests"
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
    workflow.add_node("create_report", node_create_report)
    
    workflow.set_entry_point("analyze_repository")
    
    workflow.add_edge("analyze_repository", "create_test_plan")
    workflow.add_edge("create_test_plan", "generate_tests")
    workflow.add_edge("generate_tests", "run_tests")
    workflow.add_edge("run_tests", "analyze_failures")
    
    workflow.add_conditional_edges("analyze_failures", should_repair, {
        "repair_tests": "repair_tests",
        "create_report": "create_report"
    })
    
    workflow.add_edge("repair_tests", "run_tests_again")
    workflow.add_edge("run_tests_again", "analyze_failures") # Loop back to check if it worked
    
    workflow.add_edge("create_report", END)
    
    return workflow.compile()

app = build_graph()

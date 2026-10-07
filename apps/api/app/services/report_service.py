import os
import re
from sqlalchemy.orm import Session
from apps.api.app.core.config import settings
from apps.api.app.models.run import Run, TestCase, TestResult, FailureRecord, RepairAttempt
from apps.api.app.models.project import Project

# LangGraph's default recursion limit (25) is too low for unit + e2e phases with repair loops
GRAPH_RECURSION_LIMIT = 60


def run_pipeline(run_id: str, project: Project, repository_path: str) -> dict:
    from packages.agent_core.graph import app as graph_app

    initial_state = {
        "project_id": project.id,
        "run_id": run_id,
        "repository_path": repository_path,
        "test_types": project.test_types or ["unit"],
        "app_url": project.app_url,
        "phase": "unit",
        "codebase_summary": {},
        "test_plan": {},
        "e2e_plan": {},
        "generated_tests": [],
        "execution_results": {},
        "failures": [],
        "repair_attempts": 0,
        "repairs": [],
        "final_report": {}
    }
    return graph_app.invoke(initial_state, config={"recursion_limit": GRAPH_RECURSION_LIMIT})


def save_results(run_id: str, state: dict, db: Session):
    # Save Test Cases
    test_case_map = {}
    for test in state.get("generated_tests", []):
        tc = TestCase(
            run_id=run_id,
            name=test["name"],
            file_path=test["file_path"],
            test_code=test["test_code"],
            test_type=test.get("test_type", "unit"),
            status="GENERATED"
        )
        db.add(tc)
        db.flush()
        test_case_map[test["name"]] = tc.id
        
    # Save Execution Results
    for name, result in state.get("execution_results", {}).items():
        tc_id = test_case_map.get(name)
        if tc_id:
            tr = TestResult(
                run_id=run_id,
                test_case_id=tc_id,
                status=result["status"],
                stdout=result["stdout"],
                stderr=result["stderr"],
                duration_ms=result["duration_ms"],
                artifacts=result.get("artifacts") or [],
                cases=result.get("cases") or [],
            )
            db.add(tr)
            
    # Save Failures
    for failure in state.get("failures", []):
        tc_id = test_case_map.get(failure.get("test_name"))
        if tc_id:
            fr = FailureRecord(
                run_id=run_id,
                test_case_id=tc_id,
                category=failure["category"],
                explanation=failure["explanation"],
                evidence=failure["evidence"]
            )
            db.add(fr)

    # Save Repair Attempts
    final_results = state.get("execution_results", {})
    for repair in state.get("repairs", []):
        tc_id = test_case_map.get(repair.get("test_name"))
        if tc_id:
            db.add(RepairAttempt(
                run_id=run_id,
                test_case_id=tc_id,
                attempt_number=repair.get("attempt_number", 1),
                patch=repair.get("patch", ""),
                result=repair.get("explanation", ""),
            ))

    db.flush()

    run = db.query(Run).filter(Run.id == run_id).first()
    if run:
        run.summary = build_report(run, db)["summary"]

    db.commit()


def _parse_counts(tc: TestCase, tr: TestResult | None) -> tuple[int, int, int, list]:
    """Return (generated, passed, failed, individual_tests) for one test file."""
    tc_generated = tc.test_code.count("def test_") if tc.test_code else 1
    tc_passed = 0
    tc_failed = 0
    individual = []

    if tr and tr.cases:
        individual = [{**case, "file": tc.name, "test_type": tc.test_type or "unit"} for case in tr.cases]
        passed = sum(c["status"] == "PASSED" for c in individual)
        failed = sum(c["status"] in ("FAILED", "ERROR") for c in individual)
        return len(individual), passed, failed, individual

    if tr:
        output = (tr.stdout or "") + "\n" + (tr.stderr or "")
        passed_match = re.search(r'(\d+) passed', output)
        failed_match = re.search(r'(\d+) failed', output)
        error_match = re.search(r'(\d+) error', output)

        if passed_match: tc_passed = int(passed_match.group(1))
        if failed_match: tc_failed = int(failed_match.group(1))

        if error_match or (tc_passed == 0 and tc_failed == 0 and tr.status != "PASSED"):
            tc_failed = max(tc_generated - tc_passed, tc_failed)

        if tc_passed == 0 and tc_failed == 0 and tr.status == "PASSED":
            tc_passed = tc_generated

        # Parse individual test names from verbose output
        if tr.stdout:
            for line in tr.stdout.split("\n"):
                match = re.search(r'::([^ ]+) (PASSED|FAILED|ERROR|SKIPPED)', line)
                if match:
                    individual.append({
                        "name": match.group(1),
                        "status": match.group(2),
                        "file": tc.name,
                        "test_type": tc.test_type or "unit",
                    })
    else:
        tc_failed = tc_generated

    return max(tc_generated, tc_passed + tc_failed), tc_passed, tc_failed, individual


def _artifact_url(run_id: str, abs_path: str) -> str | None:
    base = os.path.abspath(os.path.join(settings.workspace_dir, "artifacts", run_id))
    abs_path = os.path.abspath(abs_path)
    if not abs_path.startswith(base + os.sep):
        return None
    rel = os.path.relpath(abs_path, base)
    return f"/api/v1/runs/{run_id}/artifacts/{rel}"


def build_report(run: Run, db: Session) -> dict:
    run_id = run.id
    test_cases = db.query(TestCase).filter(TestCase.run_id == run_id).all()
    test_results = db.query(TestResult).filter(TestResult.run_id == run_id).all()
    failures = db.query(FailureRecord).filter(FailureRecord.run_id == run_id).all()
    repairs = db.query(RepairAttempt).filter(RepairAttempt.run_id == run_id).order_by(RepairAttempt.attempt_number).all()

    tc_by_id = {tc.id: tc for tc in test_cases}
    total_generated = total_passed = total_failed = 0
    all_tests = []
    test_files = []

    for tc in test_cases:
        tr = next((r for r in test_results if r.test_case_id == tc.id), None)
        gen, passed, failed, individual = _parse_counts(tc, tr)
        total_generated += gen
        total_passed += passed
        total_failed += failed
        all_tests.extend(individual)

        test_files.append({
            "id": tc.id,
            "name": tc.name,
            "test_type": tc.test_type or "unit",
            "status": tr.status if tr else "UNKNOWN",
            "code": tc.test_code,
            "stdout": tr.stdout if tr else None,
            "stderr": tr.stderr if tr else None,
            "duration_ms": tr.duration_ms if tr else None,
            "passed": passed,
            "failed": failed,
            "artifacts": [u for u in (_artifact_url(run_id, p) for p in ((tr.artifacts if tr else None) or [])) if u],
        })

    # If no verbose tests found (old run), fallback to files
    if not all_tests:
        all_tests = [{"name": f["name"], "status": f["status"], "file": f["name"], "test_type": f["test_type"]}
                     for f in test_files]

    # Remove duplicates
    seen = set()
    unique_tests = []
    for t in all_tests:
        key = (t.get("file"), t["name"])
        if key not in seen:
            seen.add(key)
            unique_tests.append(t)

    # A file counts as "repaired" if it was patched and ended up passing
    status_by_tc = {f["id"]: f["status"] for f in test_files}
    repaired_files = {r.test_case_id for r in repairs if status_by_tc.get(r.test_case_id) == "PASSED"}

    return {
        "run_id": run_id,
        "project_id": run.project_id,
        "status": run.status,
        "status_reason": run.status_reason,
        "summary": {
            "generated": total_generated,
            "passed": total_passed,
            "failed": total_failed,
            "repaired": len(repaired_files),
            "files": len(test_files),
        },
        "tests": unique_tests,
        "test_files": test_files,
        "failures": [
            {
                "test_name": tc_by_id[f.test_case_id].name if f.test_case_id in tc_by_id else None,
                "category": f.category,
                "explanation": f.explanation,
                "evidence": f.evidence or [],
            } for f in failures
        ],
        "repairs": [
            {
                "test_name": tc_by_id[r.test_case_id].name if r.test_case_id in tc_by_id else None,
                "attempt_number": r.attempt_number,
                "patch": r.patch,
                "explanation": r.result,
            } for r in repairs
        ],
    }


def get_report(run_id: str, db: Session) -> dict:
    db_run = db.query(Run).filter(Run.id == run_id).first()
    if not db_run:
        return {}
    return build_report(db_run, db)

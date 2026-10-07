from sqlalchemy.orm import Session
from apps.api.app.models.run import Run, TestCase, TestResult, FailureRecord, RepairAttempt
from packages.agent_core.graph import app as graph_app
from datetime import datetime
import json

def trigger_run_sync(run_id: str, project_id: str, repository_path: str, db: Session):
    db_run = db.query(Run).filter(Run.id == run_id).first()
    if not db_run:
        return
        
    db_run.status = "RUNNING"
    db_run.started_at = datetime.utcnow()
    db.commit()
    
    initial_state = {
        "project_id": project_id,
        "run_id": run_id,
        "repository_path": repository_path,
        "codebase_summary": {},
        "test_plan": {},
        "generated_tests": [],
        "execution_results": {},
        "failures": [],
        "repair_attempts": 0,
        "final_report": {}
    }
    
    try:
        # Run graph
        final_state = graph_app.invoke(initial_state)
        
        # Save results to DB
        save_results(run_id, final_state, db)
        
        db_run.status = "COMPLETED"
        
    except Exception as e:
        db_run.status = "FAILED"
        db_run.status_reason = str(e)
        
    db_run.finished_at = datetime.utcnow()
    db.commit()

def save_results(run_id: str, state: dict, db: Session):
    # Save Test Cases
    test_case_map = {}
    for test in state.get("generated_tests", []):
        tc = TestCase(
            run_id=run_id,
            name=test["name"],
            file_path=test["file_path"],
            test_code=test["test_code"],
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
                duration_ms=result["duration_ms"]
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
            
    db.commit()

import re

def get_report(run_id: str, db: Session) -> dict:
    db_run = db.query(Run).filter(Run.id == run_id).first()
    if not db_run:
        return {}
        
    test_cases = db.query(TestCase).filter(TestCase.run_id == run_id).all()
    test_results = db.query(TestResult).filter(TestResult.run_id == run_id).all()
    failures = db.query(FailureRecord).filter(FailureRecord.run_id == run_id).all()
    
    total_generated = 0
    total_passed = 0
    total_failed = 0
    
    all_tests = []
    
    for tc in test_cases:
        tr = next((tr for tr in test_results if tr.test_case_id == tc.id), None)
        
        tc_generated = tc.test_code.count("def test_") if tc.test_code else 1
        tc_passed = 0
        tc_failed = 0
        
        if tr:
            output = (tr.stdout or "") + "\n" + (tr.stderr or "")
            passed_match = re.search(r'(\d+) passed', output)
            failed_match = re.search(r'(\d+) failed', output)
            error_match = re.search(r'(\d+) error', output)
            
            if passed_match: tc_passed = int(passed_match.group(1))
            if failed_match: tc_failed = int(failed_match.group(1))
            
            if error_match or (tc_passed == 0 and tc_failed == 0 and tr.status != "PASSED"):
                tc_failed = tc_generated - tc_passed
                
            if tc_passed == 0 and tc_failed == 0 and tr.status == "PASSED":
                tc_passed = tc_generated
                
            # Parse individual test names from verbose output
            if tr.stdout:
                for line in tr.stdout.split("\n"):
                    match = re.search(r'::([^ ]+) (PASSED|FAILED|ERROR|SKIPPED)', line)
                    if match:
                        all_tests.append({
                            "name": match.group(1),
                            "status": match.group(2)
                        })
        else:
            tc_failed = tc_generated
            
        total_generated += max(tc_generated, tc_passed + tc_failed)
        total_passed += tc_passed
        total_failed += tc_failed
        
    # If no verbose tests found (old run), fallback to files
    if not all_tests:
        all_tests = [
            {
                "name": tc.name,
                "status": next((tr.status for tr in test_results if tr.test_case_id == tc.id), "UNKNOWN")
            } for tc in test_cases
        ]
        
    # Remove duplicates
    seen = set()
    unique_tests = []
    for t in all_tests:
        if t["name"] not in seen:
            seen.add(t["name"])
            unique_tests.append(t)
    
    return {
        "run_id": run_id,
        "project_id": db_run.project_id,
        "status": db_run.status,
        "summary": {
            "generated": total_generated,
            "passed": total_passed,
            "failed": total_failed,
            "repaired": 0
        },
        "tests": unique_tests,
        "failures": [
            {
                "category": f.category,
                "explanation": f.explanation
            } for f in failures
        ]
    }

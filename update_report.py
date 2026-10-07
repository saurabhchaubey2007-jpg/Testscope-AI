import re

def parse_pytest_output(stdout: str, stderr: str, test_code: str):
    output = stdout + "\n" + stderr
    
    # Total tests generated based on source code
    total_generated = test_code.count("def test_")
    
    passed = 0
    failed = 0
    
    # Try to parse the summary line, e.g. "1 failed, 17 passed in 0.12s"
    # match patterns like "(\d+) passed", "(\d+) failed", "(\d+) error"
    passed_match = re.search(r'(\d+) passed', output)
    if passed_match:
        passed = int(passed_match.group(1))
        
    failed_match = re.search(r'(\d+) failed', output)
    if failed_match:
        failed += int(failed_match.group(1))
        
    error_match = re.search(r'(\d+) error', output)
    if error_match:
        # If there's a collection error (e.g. syntax error), consider all tests as failed
        failed += total_generated
        
    # If it passed completely but didn't print "failed", and total generated > 0
    if passed == 0 and failed == 0:
        if "ERROR" in output or "FAILED" in output:
            failed = total_generated
        elif "PASSED" in output:
            passed = total_generated
            
    # Fallback to file-level status if parsing fails
    if passed == 0 and failed == 0 and total_generated > 0:
        if "=== ERRORS ===" in output or "failed" in output.lower():
            failed = total_generated
        else:
            passed = total_generated

    # Ensure we don't undercount
    if passed + failed < total_generated and error_match:
        failed = total_generated - passed
        
    return total_generated, passed, failed

with open('apps/api/app/services/report_service.py', 'r') as f:
    content = f.read()

# Replace the get_report function logic
new_func = """import re

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
    
    for tc in test_cases:
        tr = next((tr for tr in test_results if tr.test_case_id == tc.id), None)
        
        tc_generated = tc.test_code.count("def test_") if tc.test_code else 1
        tc_passed = 0
        tc_failed = 0
        
        if tr:
            output = (tr.stdout or "") + "\\n" + (tr.stderr or "")
            passed_match = re.search(r'(\\d+) passed', output)
            failed_match = re.search(r'(\\d+) failed', output)
            error_match = re.search(r'(\\d+) error', output)
            
            if passed_match: tc_passed = int(passed_match.group(1))
            if failed_match: tc_failed = int(failed_match.group(1))
            
            if error_match or (tc_passed == 0 and tc_failed == 0 and tr.status != "PASSED"):
                tc_failed = tc_generated - tc_passed
                
            if tc_passed == 0 and tc_failed == 0 and tr.status == "PASSED":
                tc_passed = tc_generated
        else:
            tc_failed = tc_generated
            
        total_generated += tc_generated
        total_passed += tc_passed
        total_failed += tc_failed
    
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
        "tests": [
            {
                "name": tc.name,
                "status": next((tr.status for tr in test_results if tr.test_case_id == tc.id), "UNKNOWN")
            } for tc in test_cases
        ],
        "failures": [
            {
                "category": f.category,
                "explanation": f.explanation
            } for f in failures
        ]
    }
"""

content = re.sub(r'def get_report\(run_id: str, db: Session\) -> dict:.*', new_func, content, flags=re.DOTALL)

with open('apps/api/app/services/report_service.py', 'w') as f:
    f.write(content)

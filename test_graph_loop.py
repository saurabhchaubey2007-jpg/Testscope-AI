import sys
from packages.agent_core.graph import app as graph_app

initial_state = {
    "project_id": "test",
    "run_id": "c612a4d1-a367-468d-8f20-8ed132e0e856",
    "repository_path": "./workspace/repositories/sample_app",
    "codebase_summary": {},
    "test_plan": {},
    "generated_tests": [{"name": "test_dummy", "file_path": "/tmp/nonexistent.py", "test_code": "import nonexistent"}],
    "execution_results": {"test_dummy": {"status": "FAILED", "stdout": "ModuleNotFoundError: nonexistent", "stderr": ""}},
    "failures": [{"test_name": "test_dummy", "category": "TEST_DEFECT", "explanation": "test", "evidence": [], "needs_review": False}],
    "repair_attempts": 0,
    "final_report": {}
}

# We bypass earlier nodes by starting from repair_tests or just running the whole thing, but we can't easily start midway without a checkpointer.

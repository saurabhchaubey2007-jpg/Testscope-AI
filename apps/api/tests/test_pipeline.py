import os
import pytest
from apps.api.app.services.repository_analyzer import analyze_repository
from apps.api.app.services.test_planner import TestPlan
from apps.api.app.services.test_generator import GeneratedTestSuite
from apps.api.app.services.test_executor import run_pytest
from apps.api.app.services.failure_analyzer import deterministic_classify
import packages.llm_router.router as router

def test_repository_analyzer():
    repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../workspace/repositories/sample_app"))
    summary = analyze_repository(repo_path)
    assert summary["files"] == 1
    assert "main" in summary["modules"]
    function_names = [f["name"] for f in summary["functions"]]
    assert "add" in function_names
    assert "divide" in function_names

def test_llm_abstraction(monkeypatch):
    monkeypatch.setenv("USE_FAKE_LLM", "true")
    # Just ensure it doesn't crash and returns an instance
    plan = router.generate_structured("prompt", TestPlan)
    assert isinstance(plan, TestPlan)
    
def test_test_executor():
    repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../workspace/repositories/sample_app"))
    # Create a dummy test file
    test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../workspace/generated_tests/test_run"))
    os.makedirs(test_dir, exist_ok=True)
    test_file_path = os.path.join(test_dir, "test_dummy.py")
    with open(test_file_path, "w") as f:
        f.write("def test_dummy():\n    assert True\n")
        
    results = run_pytest([{"name": "test_dummy", "file_path": test_file_path}], repo_path)
    assert "test_dummy" in results
    assert results["test_dummy"]["status"] == "PASSED"

def test_deterministic_classify():
    assert deterministic_classify("ModuleNotFoundError: No module named 'foo'", "") == "TEST_DEFECT"
    assert deterministic_classify("SyntaxError: invalid syntax", "") == "TEST_DEFECT"
    assert deterministic_classify("E       fixture 'foo' not found", "") == "TEST_DEFECT"
    assert deterministic_classify("AssertionError: assert 1 == 2", "") is None

from typing import TypedDict, List, Dict, Any, Optional

class TestScopeState(TypedDict):
    project_id: str
    run_id: str
    repository_path: str
    codebase_summary: dict
    test_plan: dict
    generated_tests: list
    execution_results: dict
    failures: list
    repair_attempts: int
    final_report: dict

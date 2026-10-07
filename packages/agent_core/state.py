from typing import TypedDict, List, Dict, Any, Optional

class TestScopeState(TypedDict, total=False):
    project_id: str
    run_id: str
    repository_path: str
    # Which kinds of tests to generate: ["unit"], ["e2e"] or both
    test_types: list
    # Base URL of the running application (E2E only)
    app_url: Optional[str]
    # Current pipeline phase: "unit" or "e2e"
    phase: str
    codebase_summary: dict
    test_plan: dict
    e2e_plan: dict
    generated_tests: list
    execution_results: dict
    failures: list
    # Repair attempts within the current phase (drives the repair loop)
    repair_attempts: int
    # Every repair made across the whole run
    repairs: list
    final_report: dict

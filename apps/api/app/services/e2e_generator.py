"""Playwright (Python, pytest-playwright) E2E test planning and generation."""
import json
import os
from typing import List

from pydantic import BaseModel, Field

from apps.api.app.core.config import settings
from packages.llm_router.router import generate_structured, generate_python_suite
from apps.api.app.services.test_generator import safe_test_path


class E2EScenario(BaseModel):
    name: str = Field(description="Short name of the user flow, e.g. 'login with valid credentials'")
    steps: List[str] = Field(default_factory=list, description="User actions in order")
    expected: str = Field(default="", description="What the user should observe at the end")
    priority: str = Field(default="Medium", description="High, Medium, Low")


class E2EPlan(BaseModel):
    scenarios: List[E2EScenario] = Field(default_factory=list)


class GeneratedE2ETest(BaseModel):
    file_name: str = Field(description="Name of the test file, must start with test_e2e_")
    code: str = Field(description="Complete Python pytest-playwright test code")


class GeneratedE2ESuite(BaseModel):
    tests: List[GeneratedE2ETest] = Field(default_factory=list)

    @classmethod
    def fake(cls):
        return cls(tests=[GeneratedE2ETest(
            file_name="test_e2e_smoke.py",
            code=(
                "from playwright.sync_api import Page\n\n\n"
                "def test_homepage_loads(page: Page, base_url):\n"
                "    response = page.goto(base_url)\n"
                "    assert response is not None and response.ok\n"
            ),
        )])


def create_e2e_plan(codebase_summary: dict, app_url: str) -> dict:
    prompt = f"""
    You are planning end-to-end browser tests for a web application running at {app_url}.
    Using the codebase summary below (routes, templates, components, API handlers),
    identify the most important user flows to verify through the UI.
    Prefer 3-6 high-value, deterministic scenarios (navigation, forms, key pages rendering).
    Avoid flows that require real third-party accounts, payments or emails.

    Codebase Summary:
    {json.dumps(codebase_summary, indent=2)[:40000]}
    """
    plan = generate_structured(prompt, E2EPlan)
    return plan.model_dump()


def generate_e2e_tests(e2e_plan: dict, app_url: str, run_id: str) -> list:
    prompt = f"""
    Write Python end-to-end tests using pytest-playwright for the app at {app_url}.

    Rules:
    - Use the sync API: `from playwright.sync_api import Page, expect`.
    - Each test takes the `page: Page` fixture; use the `base_url` fixture or relative
      paths with `page.goto("/")` (base URL is passed via --base-url).
    - Prefer role/text based locators (`page.get_by_role`, `page.get_by_text`, `page.get_by_label`).
    - Use `expect(...)` assertions, never `time.sleep`.
    - Keep tests independent and deterministic. Do not hit external sites.
    - Group related scenarios in the same file. File names must start with test_e2e_.

    E2E Plan:
    {json.dumps(e2e_plan, indent=2)}
    """
    suite = generate_python_suite(prompt, GeneratedE2ESuite, "test_e2e_generated.py")

    generated_dir = os.path.join(settings.workspace_dir, "generated_tests", run_id, "e2e")
    os.makedirs(generated_dir, exist_ok=True)

    results = []
    for test in suite.tests:
        file_name = test.file_name
        if not file_name.startswith("test_"):
            file_name = "test_e2e_" + file_name
        if not file_name.endswith(".py"):
            file_name += ".py"

        file_path = safe_test_path(generated_dir, file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(test.code)

        results.append({
            "name": file_name,
            "file_path": file_path,
            "test_code": test.code,
            "test_type": "e2e",
        })
    return results


def e2e_artifacts_dir(run_id: str) -> str:
    path = os.path.abspath(os.path.join(settings.workspace_dir, "artifacts", run_id))
    os.makedirs(path, exist_ok=True)
    return path


def playwright_args(app_url: str) -> list:
    return [
        "--base-url", app_url,
        "--browser", "chromium",
        "--screenshot", "only-on-failure",
        "--tracing", "retain-on-failure",
    ]

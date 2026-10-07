"""Regression coverage for Phase 2 boundaries and worker behavior."""
import os
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from apps.api.app.main import app, run_migrations
from apps.api.app.core.config import settings
from apps.api.app.core.database import SessionLocal
from apps.api.app.models.run import Run, TestCase as Case, TestResult as Result
from apps.api.app.services import run_worker, git_service
from apps.api.app.services.failure_analyzer import analyze_failures
from apps.api.app.services.report_service import _parse_counts
from apps.api.app.services.test_executor import run_pytest
from apps.api.app.services.test_generator import safe_test_path
from packages.agent_core.graph import app as graph


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.post("/api/v1/auth/register", json={"email": "phase2@example.com", "password": "password123"})
        yield c


@pytest.fixture
def project(client, tmp_path):
    (tmp_path / "main.py").write_text("def add(a, b):\n    return a + b\n")
    return client.post("/api/v1/projects/", json={"name": "Phase 2", "repository_path": str(tmp_path)}).json()


def test_queued_run_returns_before_pipeline_and_can_be_cancelled(client, project, monkeypatch):
    queued = []
    monkeypatch.setattr("apps.api.app.api.routes.projects.enqueue_run", lambda *args: queued.append(args))
    run = client.post(f"/api/v1/projects/{project['id']}/runs", json={}).json()
    assert run["status"] == "QUEUED" and queued[0][0] == run["id"]
    assert client.delete(f"/api/v1/projects/{project['id']}").status_code == 409
    assert client.post(f"/api/v1/runs/{run['id']}/cancel").json()["status"] == "cancelled"
    run_worker.execute_run(run["id"])
    assert client.get(f"/api/v1/runs/{run['id']}").json()["status"] == "CANCELLED"
    assert client.get(f"/api/v1/runs/{run['id']}/events").json()[0]["message"] == "Cancellation requested"


def test_settings_provider_and_github_token_are_private(client):
    user = client.patch("/api/v1/auth/me", json={"llm_provider": "groq", "github_token": "test-pat"}).json()
    assert user["llm_provider"] == "groq" and user["has_github_token"] is True
    assert "github_token" not in user
    assert client.patch("/api/v1/auth/me", json={"llm_provider": "invalid"}).status_code == 422
    assert client.patch("/api/v1/auth/me", json={"github_token": ""}).json()["has_github_token"] is False


def test_run_data_and_artifacts_are_scoped_to_owner(client, project):
    run_id = client.post(f"/api/v1/projects/{project['id']}/runs", json={}).json()["id"]
    artifacts = Path(settings.workspace_dir) / "artifacts" / run_id
    artifacts.mkdir(parents=True)
    (artifacts / "trace.zip").write_bytes(b"example")
    assert client.get(f"/api/v1/runs/{run_id}/artifacts/trace.zip").status_code == 200
    client.cookies.clear()
    client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "password123"})
    for suffix in ("", "/events", "/report", "/artifacts/trace.zip"):
        assert client.get(f"/api/v1/runs/{run_id}{suffix}").status_code == 404
    assert client.post(f"/api/v1/runs/{run_id}/cancel").status_code == 404


def test_node_cancellation_prevents_the_next_step(client, project):
    from packages.agent_core.graph import node_analyze_repository
    from apps.api.app.services.run_events import RunCancelled
    with SessionLocal() as db:
        run = Run(project_id=project["id"], status="CANCELLED")
        db.add(run); db.commit(); run_id = run.id
    with pytest.raises(RunCancelled):
        node_analyze_repository({"run_id": run_id, "repository_path": project["repository_path"]})


def test_cancelled_running_project_cannot_be_deleted(client, project):
    with SessionLocal() as db:
        db.add(Run(project_id=project["id"], status="CANCELLED", started_at=datetime.utcnow()))
        db.commit()
    assert client.delete(f"/api/v1/projects/{project['id']}").status_code == 409


def test_migrations_create_and_upgrade_sqlite(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migrations.db'}"
    monkeypatch.setattr(settings, "database_url", url)
    run_migrations()
    run_migrations()  # Starting twice must be safe.
    engine = create_engine(url)
    inspector = inspect(engine)
    assert "run_events" in inspector.get_table_names()
    assert "llm_provider" in {c["name"] for c in inspector.get_columns("users")}
    assert "cases" in {c["name"] for c in inspector.get_columns("test_results")}
    engine.dispose()


@pytest.mark.parametrize("filename", ["../test_escape.py", "test_/../../escape.py", "/tmp/test_escape.py", "test_\\escape.py"])
def test_generated_filename_cannot_escape_workspace(tmp_path, filename):
    with pytest.raises(ValueError):
        safe_test_path(str(tmp_path), filename)


def test_structured_results_include_parameterized_and_skipped_tests(tmp_path):
    path = tmp_path / "test_counts.py"
    path.write_text("import pytest\n@pytest.mark.parametrize('n', [1,2,3])\ndef test_numbers(n):\n    assert n > 0\n@pytest.mark.skip(reason='example')\ndef test_skip():\n    pass\n")
    result = run_pytest([{"name": path.name, "file_path": str(path)}], str(tmp_path))[path.name]
    assert [c["status"] for c in result["cases"]] == ["PASSED"] * 3 + ["SKIPPED"]
    counts = _parse_counts(Case(name=path.name, test_code=path.read_text(), test_type="unit"), Result(status=result["status"], cases=result["cases"]))
    assert counts[:3] == (4, 3, 0)


def test_execution_timeout_is_reported_as_environment_failure():
    failures = analyze_failures({"test_timeout": {"status": "TIMEOUT", "stderr": "Timed out"}}, [])
    assert failures[0]["category"] == "ENV_FAILURE"


def test_e2e_branch_records_artifacts_without_unit_generation(monkeypatch, tmp_path):
    import packages.agent_core.graph as graph_module
    monkeypatch.setattr(graph_module, "generate_e2e_tests", lambda *args: [
        {"name": "test_e2e.py", "file_path": str(tmp_path / "test_e2e.py"), "test_code": "def test_page(): pass", "test_type": "e2e"}])
    executed = []
    def fake_execute(tests, repository_path, **kwargs):
        executed.append(kwargs)
        return {"test_e2e.py": {"status": "PASSED", "stdout": "", "stderr": "", "duration_ms": 1, "artifacts": ["trace.zip"]}}
    monkeypatch.setattr(graph_module, "run_pytest", fake_execute)
    state = graph.invoke({"run_id": "", "repository_path": str(tmp_path), "test_types": ["e2e"], "app_url": "http://localhost:3000"})
    assert state["phase"] == "e2e" and len(state["generated_tests"]) == 1
    assert "--base-url" in executed[0]["extra_args"]
    assert state["execution_results"]["test_e2e.py"]["artifacts"] == ["trace.zip"]


def test_github_credentials_not_in_url_and_pr_sha_pinned(tmp_path, monkeypatch):
    calls = []
    def fake_git(args, **kwargs):
        calls.append(args)
        return "a" * 40
    monkeypatch.setattr(git_service, "_git", fake_git)
    sha = git_service.checkout("https://github.com/org/repo", str(tmp_path / "clone"), ref="a" * 40, pr_number=2, token="test-token")
    assert sha == "a" * 40
    assert all("test-token" not in str(args) for args in calls)
    assert ["fetch", "--depth", "1", "https://github.com/org/repo", "a" * 40] in calls


def test_provider_preference_uses_context_without_changing_global_settings(monkeypatch):
    from packages.llm_router import router
    monkeypatch.setenv("USE_FAKE_LLM", "false")
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(settings, "groq_model", "test-model")
    monkeypatch.setattr(router, "ChatGroq", lambda **kwargs: kwargs)
    original_provider = settings.default_llm_provider
    token = router.active_provider.set("groq")
    try:
        assert router.get_llm()["model"] == "test-model"
        assert settings.default_llm_provider == original_provider
    finally:
        router.active_provider.reset(token)
    assert router.active_provider.get() is None


@pytest.mark.parametrize("category,expected_repairs", [("TEST_DEFECT", 3), ("APP_DEFECT", 0)])
def test_repair_loop_is_bounded_and_leaves_application_defects(monkeypatch, tmp_path, category, expected_repairs):
    import packages.agent_core.graph as graph_module
    monkeypatch.setattr(graph_module, "generate_tests", lambda *args: [
        {"name": "test_example.py", "file_path": "unused", "test_code": "assert False", "test_type": "unit"}])
    monkeypatch.setattr(graph_module, "run_pytest", lambda *args, **kwargs: {
        "test_example.py": {"status": "FAILED", "stdout": "AssertionError", "stderr": "", "duration_ms": 1}})
    monkeypatch.setattr(graph_module, "analyze_failures", lambda *args: [
        {"test_name": "test_example.py", "category": category, "explanation": "test", "evidence": []}])
    repairs = []
    monkeypatch.setattr(graph_module, "repair_tests", lambda *args: repairs.append(True) or [])
    state = graph.invoke({"run_id": "", "repository_path": str(tmp_path), "test_types": ["unit"]})
    assert len(repairs) == expected_repairs
    assert state["failures"][0]["category"] == category


def test_playwright_failure_collects_screenshot_and_trace(tmp_path):
    from playwright.sync_api import sync_playwright
    from apps.api.app.services.e2e_generator import playwright_args
    with sync_playwright() as playwright:
        if not Path(playwright.chromium.executable_path).exists():
            pytest.skip("Run make playwright to install Chromium")
    path = tmp_path / "test_browser_failure.py"
    path.write_text("from playwright.sync_api import expect\ndef test_failure(page):\n    page.set_content('<h1>Checkout</h1>')\n    expect(page.get_by_role('heading')).to_have_text('Broken', timeout=100)\n")
    result = run_pytest([{"name": path.name, "file_path": str(path)}], str(tmp_path),
                        extra_args=playwright_args("http://localhost"), artifacts_dir=str(tmp_path / "artifacts"), timeout=30)[path.name]
    assert result["status"] == "FAILED"
    assert result["cases"][0]["status"] == "FAILED"
    assert any(p.endswith(".png") for p in result["artifacts"])
    assert any(p.endswith(".zip") for p in result["artifacts"])

import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import app

SAMPLE_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../workspace/repositories/sample_app"))


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def register(client, email="dev@example.com", password="password123"):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password, "name": "Dev"})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def auth_client(client):
    register(client)
    return client


@pytest.fixture
def sample_repo(tmp_path):
    # Use the bundled sample app when available, otherwise create a tiny repo
    if os.path.isdir(SAMPLE_REPO):
        return SAMPLE_REPO
    repo = tmp_path / "sample_app"
    repo.mkdir()
    (repo / "main.py").write_text("def add(a, b):\n    return a + b\n")
    return str(repo)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200


# ---------- auth ----------

def test_register_login_me(client):
    register(client)
    assert client.get("/api/v1/auth/me").json()["email"] == "dev@example.com"

    client.post("/api/v1/auth/logout")
    client.cookies.clear()
    assert client.get("/api/v1/auth/me").status_code == 401

    r = client.post("/api/v1/auth/login", json={"email": "dev@example.com", "password": "password123"})
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200


def test_login_wrong_password(client):
    register(client)
    client.cookies.clear()
    r = client.post("/api/v1/auth/login", json={"email": "dev@example.com", "password": "nope-nope"})
    assert r.status_code == 401


def test_duplicate_register(client):
    register(client)
    r = client.post("/api/v1/auth/register", json={"email": "dev@example.com", "password": "password123"})
    assert r.status_code == 400


def test_bearer_token_auth(client):
    token = register(client)["access_token"]
    client.cookies.clear()
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_projects_require_auth(client):
    assert client.get("/api/v1/projects/").status_code == 401


# ---------- projects ----------

def test_create_and_list_project(auth_client, sample_repo):
    r = auth_client.post("/api/v1/projects/", json={"name": "Sample Project", "repository_path": sample_repo})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "Sample Project"
    assert data["source_type"] == "local"

    projects = auth_client.get("/api/v1/projects/").json()
    assert len(projects) == 1


def test_local_project_missing_dir(auth_client):
    r = auth_client.post("/api/v1/projects/", json={"name": "x", "repository_path": "/definitely/not/here"})
    assert r.status_code == 400


def test_e2e_requires_app_url(auth_client, sample_repo):
    r = auth_client.post("/api/v1/projects/", json={
        "name": "x", "repository_path": sample_repo, "test_types": ["unit", "e2e"],
    })
    assert r.status_code == 422


def test_github_project_gets_webhook_secret(auth_client):
    r = auth_client.post("/api/v1/projects/", json={
        "name": "gh", "source_type": "github", "repo_url": "https://github.com/octocat/Hello-World",
    })
    assert r.status_code == 200, r.text
    assert r.json()["webhook_secret"]


def test_github_project_rejects_bad_url(auth_client):
    r = auth_client.post("/api/v1/projects/", json={
        "name": "gh", "source_type": "github", "repo_url": "https://gitlab.com/a/b",
    })
    assert r.status_code == 400


def test_projects_are_isolated_between_users(client, sample_repo):
    register(client, "a@example.com")
    pid = client.post("/api/v1/projects/", json={"name": "A", "repository_path": sample_repo}).json()["id"]

    client.cookies.clear()
    register(client, "b@example.com")
    assert client.get("/api/v1/projects/").json() == []
    assert client.get(f"/api/v1/projects/{pid}").status_code == 404
    assert client.post(f"/api/v1/projects/{pid}/runs", json={}).status_code == 404


def test_delete_project(auth_client, sample_repo):
    pid = auth_client.post("/api/v1/projects/", json={"name": "A", "repository_path": sample_repo}).json()["id"]
    auth_client.post(f"/api/v1/projects/{pid}/runs", json={})
    assert auth_client.delete(f"/api/v1/projects/{pid}").status_code == 200
    assert auth_client.get(f"/api/v1/projects/{pid}").status_code == 404


# ---------- runs ----------

def test_create_run_and_report(auth_client, sample_repo):
    pid = auth_client.post("/api/v1/projects/", json={"name": "A", "repository_path": sample_repo}).json()["id"]

    r = auth_client.post(f"/api/v1/projects/{pid}/runs", json={})
    assert r.status_code == 200, r.text
    run_id = r.json()["id"]

    run = auth_client.get(f"/api/v1/runs/{run_id}").json()
    assert run["status"] == "COMPLETED", run.get("status_reason")

    events = auth_client.get(f"/api/v1/runs/{run_id}/events").json()
    steps = [e["step"] for e in events if e["event_type"] == "step_started"]
    assert steps[:4] == ["analyze_repository", "create_test_plan", "generate_tests", "run_tests"]
    assert "create_report" in steps

    report = auth_client.get(f"/api/v1/runs/{run_id}/report").json()
    assert report["summary"]["generated"] >= 1
    assert report["summary"]["passed"] >= 1
    assert report["test_files"][0]["code"]

    history = auth_client.get(f"/api/v1/projects/{pid}/runs").json()
    assert len(history) == 1
    assert auth_client.get("/api/v1/runs/").json()[0]["id"] == run_id


def test_cancel_finished_run_is_noop(auth_client, sample_repo):
    pid = auth_client.post("/api/v1/projects/", json={"name": "A", "repository_path": sample_repo}).json()["id"]
    run_id = auth_client.post(f"/api/v1/projects/{pid}/runs", json={}).json()["id"]
    assert auth_client.post(f"/api/v1/runs/{run_id}/cancel").json()["status"] == "completed"


# ---------- webhooks ----------

def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_signature_and_events(auth_client, monkeypatch):
    project = auth_client.post("/api/v1/projects/", json={
        "name": "gh", "source_type": "github", "repo_url": "https://github.com/octocat/Hello-World",
    }).json()
    pid, secret = project["id"], project["webhook_secret"]

    queued = []
    monkeypatch.setattr("apps.api.app.api.routes.webhooks.enqueue_run", lambda run_id, *a: queued.append(run_id))

    body = json.dumps({"zen": "hi"}).encode()
    url = f"/api/v1/webhooks/github/{pid}"

    # bad signature
    r = auth_client.post(url, content=body, headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": "sha256=bad"})
    assert r.status_code == 401

    # ping
    r = auth_client.post(url, content=body, headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": _sign(secret, body)})
    assert r.json()["status"] == "pong"

    # pull request opened -> queued run
    pr_body = json.dumps({
        "action": "opened",
        "pull_request": {"number": 7, "draft": False, "head": {"sha": "abc123", "ref": "feature"}},
    }).encode()
    r = auth_client.post(url, content=pr_body, headers={
        "X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _sign(secret, pr_body)})
    assert r.json()["status"] == "queued"
    assert len(queued) == 1

    run = auth_client.get(f"/api/v1/runs/{queued[0]}").json()
    assert run["pr_number"] == 7 and run["trigger"] == "webhook" and run["commit_sha"] == "abc123"

    # closed PR -> ignored
    closed = json.dumps({"action": "closed", "pull_request": {"number": 7}}).encode()
    r = auth_client.post(url, content=closed, headers={
        "X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _sign(secret, closed)})
    assert r.json()["status"] == "ignored"

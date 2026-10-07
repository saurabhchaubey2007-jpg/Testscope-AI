"""GitHub webhook receiver.

Configure in GitHub → Repo → Settings → Webhooks:
  Payload URL:  https://<public-host>/api/v1/webhooks/github/<project_id>
  Content type: application/json
  Secret:       the project's webhook secret (shown in the dashboard)
  Events:       Pull requests, Pushes
"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.models.project import Project
from apps.api.app.models.run import Run
from apps.api.app.services import git_service
from apps.api.app.services.run_worker import enqueue_run

router = APIRouter()

PR_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}


@router.post("/github/{project_id}")
async def github_webhook(
    project_id: str,
    request: Request,
    x_github_event: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id, Project.source_type == "github").first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    body = await request.body()
    if not git_service.verify_signature(project.webhook_secret or "", body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")

    if x_github_event == "ping":
        return {"status": "pong"}

    run_kwargs = None
    if x_github_event == "pull_request":
        if payload.get("action") not in PR_ACTIONS:
            return {"status": "ignored", "reason": f"action {payload.get('action')}"}
        pr = payload.get("pull_request", {})
        if pr.get("draft"):
            return {"status": "ignored", "reason": "draft PR"}
        run_kwargs = {
            "pr_number": pr.get("number"),
            "commit_sha": pr.get("head", {}).get("sha"),
            "branch": pr.get("head", {}).get("ref"),
        }
    elif x_github_event == "push":
        ref = payload.get("ref", "")
        branch = ref.removeprefix("refs/heads/")
        default = project.default_branch or payload.get("repository", {}).get("default_branch")
        if not ref.startswith("refs/heads/") or branch != default or payload.get("deleted"):
            return {"status": "ignored", "reason": "not a push to the default branch"}
        run_kwargs = {"commit_sha": payload.get("after"), "branch": branch}
    else:
        return {"status": "ignored", "reason": f"event {x_github_event}"}

    run = Run(project_id=project.id, status="QUEUED", trigger="webhook", created_at=datetime.utcnow(), **run_kwargs)
    db.add(run)
    db.commit()
    db.refresh(run)
    enqueue_run(run.id)
    return {"status": "queued", "run_id": run.id}

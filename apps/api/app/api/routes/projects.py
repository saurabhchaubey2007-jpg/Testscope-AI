import os
import secrets
import shutil
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.core.database import get_db
from apps.api.app.core.security import get_current_user
from apps.api.app.models.project import Project
from apps.api.app.models.run import Run, RunEvent, TestCase, TestResult, FailureRecord, RepairAttempt
from apps.api.app.models.user import User
from apps.api.app.schemas.project import ProjectCreate, ProjectDetailOut, ProjectOut, ProjectUpdate
from apps.api.app.schemas.run import RunCreate, RunOut
from apps.api.app.services import git_service
from apps.api.app.services.run_worker import enqueue_run

router = APIRouter()


def get_owned_project(project_id: str, user: User, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _detail(project: Project, db: Session) -> ProjectDetailOut:
    last_run = db.query(Run).filter(Run.project_id == project.id).order_by(Run.created_at.desc()).first()
    count = db.query(func.count(Run.id)).filter(Run.project_id == project.id).scalar() or 0
    out = ProjectDetailOut.model_validate(project)
    out.run_count = count
    out.last_run_status = last_run.status if last_run else None
    out.last_run_at = last_run.created_at if last_run else None
    return out


@router.get("/", response_model=list[ProjectDetailOut])
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.query(Project).filter(Project.owner_id == user.id).order_by(Project.created_at.desc()).all()
    return [_detail(p, db) for p in projects]


@router.post("/", response_model=ProjectDetailOut)
def create_project(project: ProjectCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_project = Project(
        owner_id=user.id,
        name=project.name,
        source_type=project.source_type,
        test_types=project.test_types,
        app_url=project.app_url,
        default_branch=project.default_branch,
    )

    if project.source_type == "local":
        path = os.path.abspath(project.repository_path)
        if not os.path.isdir(path):
            raise HTTPException(status_code=400, detail=f"Directory does not exist: {project.repository_path}")
        db_project.repository_path = path
    else:
        try:
            git_service.parse_github_url(project.repo_url)
        except git_service.GitError as e:
            raise HTTPException(status_code=400, detail=str(e))
        db_project.repo_url = project.repo_url.strip().removesuffix("/")
        db_project.webhook_secret = secrets.token_hex(20)

    db.add(db_project)
    db.flush()
    if project.source_type == "github":
        db_project.repository_path = git_service.clone_dir_for(db_project.id)
    db.commit()
    db.refresh(db_project)
    return _detail(db_project, db)


@router.get("/{project_id}", response_model=ProjectDetailOut)
def get_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _detail(get_owned_project(project_id, user, db), db)


@router.patch("/{project_id}", response_model=ProjectDetailOut)
def update_project(project_id: str, payload: ProjectUpdate, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    data = payload.model_dump(exclude_unset=True)
    new_types = data.get("test_types", project.test_types) or []
    new_url = data.get("app_url", project.app_url)
    if "e2e" in new_types and not new_url:
        raise HTTPException(status_code=400, detail="app_url is required when E2E tests are enabled")
    if "test_types" in data and not new_types:
        raise HTTPException(status_code=400, detail="At least one test type must be selected")
    for k, v in data.items():
        setattr(project, k, v)
    db.commit()
    db.refresh(project)
    return _detail(project, db)


@router.post("/{project_id}/webhook-secret", response_model=ProjectDetailOut)
def rotate_webhook_secret(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    if project.source_type != "github":
        raise HTTPException(status_code=400, detail="Webhooks are only available for GitHub projects")
    project.webhook_secret = secrets.token_hex(20)
    db.commit()
    db.refresh(project)
    return _detail(project, db)


@router.delete("/{project_id}")
def delete_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    if db.query(Run).filter(Run.project_id == project.id, or_(
        Run.status.in_(["QUEUED", "RUNNING"]),
        and_(Run.status == "CANCELLED", Run.started_at.is_not(None), Run.finished_at.is_(None)),
    )).first():
        raise HTTPException(status_code=409, detail="Cancel active runs and wait for them to finish before deleting the project")
    run_ids = [r.id for r in db.query(Run.id).filter(Run.project_id == project.id).all()]
    if run_ids:
        for model in (RepairAttempt, FailureRecord, TestResult, TestCase, RunEvent):
            db.query(model).filter(model.run_id.in_(run_ids)).delete(synchronize_session=False)
        db.query(Run).filter(Run.id.in_(run_ids)).delete(synchronize_session=False)
    if project.source_type == "github":
        shutil.rmtree(git_service.clone_dir_for(project.id), ignore_errors=True)
    db.delete(project)
    db.commit()
    return {"status": "deleted"}


@router.get("/{project_id}/runs", response_model=list[RunOut])
def list_project_runs(project_id: str, limit: int = 50, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    get_owned_project(project_id, user, db)
    return (db.query(Run).filter(Run.project_id == project_id)
            .order_by(Run.created_at.desc()).limit(min(limit, 200)).all())


@router.post("/{project_id}/runs", response_model=RunOut)
def create_run(project_id: str, run_req: RunCreate | None = None, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    run_req = run_req or RunCreate()

    repo_path = None
    if project.source_type == "local" and run_req.repository_path:
        repo_path = os.path.abspath(run_req.repository_path)
        if not os.path.isdir(repo_path):
            raise HTTPException(status_code=400, detail=f"Directory does not exist: {run_req.repository_path}")

    db_run = Run(
        project_id=project.id,
        status="QUEUED",
        trigger="manual",
        branch=run_req.branch or project.default_branch,
        created_at=datetime.utcnow(),
    )
    db.add(db_run)
    db.commit()
    db.refresh(db_run)

    enqueue_run(db_run.id, repo_path)
    db.refresh(db_run)
    return db_run

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.core.database import get_db
from apps.api.app.core.security import get_current_user
from apps.api.app.models.project import Project
from apps.api.app.models.run import Run, RunEvent
from apps.api.app.models.user import User
from apps.api.app.schemas.run import RunEventOut, RunOut
from apps.api.app.services.run_events import record_event

router = APIRouter()


def get_owned_run(run_id: str, user: User, db: Session) -> Run:
    run = (db.query(Run).join(Project, Project.id == Run.project_id)
           .filter(Run.id == run_id, Project.owner_id == user.id).first())
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/", response_model=list[RunOut])
def list_recent_runs(limit: int = 20, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (db.query(Run).join(Project, Project.id == Run.project_id)
            .filter(Project.owner_id == user.id)
            .order_by(Run.created_at.desc()).limit(min(limit, 100)).all())


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_owned_run(run_id, user, db)


@router.get("/{run_id}/events", response_model=list[RunEventOut])
def get_run_events(run_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_run(run_id, user, db)
    return db.query(RunEvent).filter(RunEvent.run_id == run_id).order_by(RunEvent.created_at).all()


@router.get("/{run_id}/report")
def get_run_report(run_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from apps.api.app.services.report_service import build_report
    return build_report(get_owned_run(run_id, user, db), db)


@router.post("/{run_id}/cancel")
def cancel_run(run_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_run = get_owned_run(run_id, user, db)
    if db_run.status not in ["COMPLETED", "FAILED", "CANCELLED"]:
        db_run.status = "CANCELLED"
        db.commit()
        record_event(run_id, "log", message="Cancellation requested")
    return {"status": db_run.status.lower()}


@router.get("/{run_id}/artifacts/{path:path}")
def get_artifact(run_id: str, path: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_run(run_id, user, db)
    base = os.path.abspath(os.path.join(settings.workspace_dir, "artifacts", run_id))
    full = os.path.abspath(os.path.join(base, path))
    if not full.startswith(base + os.sep) or not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(full)

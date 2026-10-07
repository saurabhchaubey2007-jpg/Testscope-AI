from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from apps.api.app.core.database import get_db
from apps.api.app.models.project import Project
from apps.api.app.schemas.project import ProjectCreate, ProjectOut
from apps.api.app.schemas.run import RunCreate, RunOut
from apps.api.app.models.run import Run
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=ProjectOut)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    db_project = Project(name=project.name, repository_path=project.repository_path)
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    return db_project

@router.post("/{project_id}/runs", response_model=RunOut)
def create_run(project_id: str, run_req: RunCreate, db: Session = Depends(get_db)):
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # In Phase 1, repository_path is provided in request to ensure it's local workspace
    db_run = Run(
        project_id=project_id,
        status="QUEUED",
        started_at=datetime.utcnow()
    )
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    
    # Start background task here or sync for Phase 1. We will hook up LangGraph here later.
    from apps.api.app.services.report_service import trigger_run_sync
    trigger_run_sync(db_run.id, db_project.id, run_req.repository_path, db)
    
    return db_run

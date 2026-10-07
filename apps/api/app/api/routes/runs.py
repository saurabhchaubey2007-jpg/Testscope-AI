from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from apps.api.app.core.database import get_db
from apps.api.app.models.run import Run
from apps.api.app.schemas.run import RunOut

router = APIRouter()

@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: str, db: Session = Depends(get_db)):
    db_run = db.query(Run).filter(Run.id == run_id).first()
    if not db_run:
        raise HTTPException(status_code=404, detail="Run not found")
    return db_run

@router.get("/{run_id}/report")
def get_run_report(run_id: str, db: Session = Depends(get_db)):
    from apps.api.app.services.report_service import get_report
    return get_report(run_id, db)

@router.post("/{run_id}/cancel")
def cancel_run(run_id: str, db: Session = Depends(get_db)):
    db_run = db.query(Run).filter(Run.id == run_id).first()
    if not db_run:
        raise HTTPException(status_code=404, detail="Run not found")
    if db_run.status not in ["COMPLETED", "FAILED", "CANCELLED"]:
        db_run.status = "CANCELLED"
        db.commit()
    return {"status": "cancelled"}

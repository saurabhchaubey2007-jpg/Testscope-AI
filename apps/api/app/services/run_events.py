"""Run progress/event recording.

Each call opens its own short-lived DB session so it is safe to use from the
background worker thread that executes the LangGraph pipeline.
"""
from datetime import datetime

from apps.api.app.core.database import SessionLocal
from apps.api.app.models.run import Run, RunEvent


class RunCancelled(Exception):
    """Raised inside the pipeline when the user cancelled the run."""


def record_event(run_id: str, event_type: str, step: str | None = None, message: str | None = None) -> None:
    db = SessionLocal()
    try:
        db.add(RunEvent(run_id=run_id, event_type=event_type, step=step, message=message, created_at=datetime.utcnow()))
        if event_type == "step_started" and step:
            run = db.query(Run).filter(Run.id == run_id).first()
            if run:
                run.current_step = step
        db.commit()
    finally:
        db.close()


def is_cancelled(run_id: str) -> bool:
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        return bool(run and run.status == "CANCELLED")
    finally:
        db.close()

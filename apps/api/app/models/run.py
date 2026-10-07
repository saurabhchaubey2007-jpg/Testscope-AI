from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, JSON
from datetime import datetime
import uuid
from apps.api.app.core.database import Base

class Run(Base):
    __tablename__ = "runs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    status = Column(String)
    status_reason = Column(String, nullable=True)
    # "manual" | "webhook"
    trigger = Column(String, default="manual")
    branch = Column(String, nullable=True)
    commit_sha = Column(String, nullable=True)
    pr_number = Column(Integer, nullable=True)
    # Name of the pipeline node currently executing (for live progress)
    current_step = Column(String, nullable=True)
    summary = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class RunEvent(Base):
    __tablename__ = "run_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), index=True)
    # "step_started" | "step_finished" | "log" | "error"
    event_type = Column(String)
    step = Column(String, nullable=True)
    message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class TestCase(Base):
    __tablename__ = "test_cases"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), index=True)
    name = Column(String)
    file_path = Column(String)
    test_code = Column(String)
    # "unit" | "e2e"
    test_type = Column(String, default="unit")
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class TestResult(Base):
    __tablename__ = "test_results"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), index=True)
    test_case_id = Column(String, ForeignKey("test_cases.id"))
    status = Column(String)
    stdout = Column(String, nullable=True)
    stderr = Column(String, nullable=True)
    duration_ms = Column(Integer)
    # Paths (relative to workspace artifacts dir) of screenshots/traces
    artifacts = Column(JSON, nullable=True)
    cases = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class FailureRecord(Base):
    __tablename__ = "failure_records"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), index=True)
    test_case_id = Column(String, ForeignKey("test_cases.id"))
    category = Column(String)
    explanation = Column(String)
    evidence = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

class RepairAttempt(Base):
    __tablename__ = "repair_attempts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), index=True)
    test_case_id = Column(String, ForeignKey("test_cases.id"))
    attempt_number = Column(Integer)
    patch = Column(String)
    result = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

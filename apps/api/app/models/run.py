from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, JSON
from datetime import datetime
import uuid
from apps.api.app.core.database import Base

class Run(Base):
    __tablename__ = "runs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"))
    status = Column(String)
    status_reason = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class TestCase(Base):
    __tablename__ = "test_cases"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"))
    name = Column(String)
    file_path = Column(String)
    test_code = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class TestResult(Base):
    __tablename__ = "test_results"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"))
    test_case_id = Column(String, ForeignKey("test_cases.id"))
    status = Column(String)
    stdout = Column(String, nullable=True)
    stderr = Column(String, nullable=True)
    duration_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class FailureRecord(Base):
    __tablename__ = "failure_records"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"))
    test_case_id = Column(String, ForeignKey("test_cases.id"))
    category = Column(String)
    explanation = Column(String)
    evidence = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

class RepairAttempt(Base):
    __tablename__ = "repair_attempts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"))
    test_case_id = Column(String, ForeignKey("test_cases.id"))
    attempt_number = Column(Integer)
    patch = Column(String)
    result = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

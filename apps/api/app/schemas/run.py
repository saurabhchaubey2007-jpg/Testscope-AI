from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any

class RunCreate(BaseModel):
    # Optional override; defaults to the project's repository path
    repository_path: Optional[str] = None
    branch: Optional[str] = None

class RunOut(BaseModel):
    id: str
    project_id: str
    status: str
    status_reason: Optional[str] = None
    trigger: Optional[str] = "manual"
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    pr_number: Optional[int] = None
    current_step: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class RunEventOut(BaseModel):
    id: str
    event_type: str
    step: Optional[str] = None
    message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

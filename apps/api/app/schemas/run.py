from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any

class RunCreate(BaseModel):
    repository_path: str

class RunOut(BaseModel):
    id: str
    project_id: str
    status: str
    status_reason: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

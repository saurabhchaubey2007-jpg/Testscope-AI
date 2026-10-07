from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ProjectCreate(BaseModel):
    name: str
    repository_path: str

class ProjectOut(BaseModel):
    id: str
    name: str
    repository_path: str
    created_at: datetime
    
    class Config:
        from_attributes = True

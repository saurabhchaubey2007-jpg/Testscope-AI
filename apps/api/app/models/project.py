from sqlalchemy import Column, String, DateTime
from datetime import datetime
import uuid
from apps.api.app.core.database import Base

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True)
    repository_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

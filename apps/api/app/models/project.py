from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from datetime import datetime
import uuid
from apps.api.app.core.database import Base

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, ForeignKey("users.id"), index=True, nullable=True)
    name = Column(String, index=True)
    # Local path on disk that the agent operates on (for GitHub projects this is the clone dir)
    repository_path = Column(String)
    # "local" | "github"
    source_type = Column(String, default="local", nullable=False)
    repo_url = Column(String, nullable=True)
    default_branch = Column(String, nullable=True)
    # ["unit"] | ["unit", "e2e"] | ["e2e"]
    test_types = Column(JSON, default=lambda: ["unit"])
    # Base URL of the running app for Playwright E2E tests
    app_url = Column(String, nullable=True)
    # Per-project secret used to verify GitHub webhook signatures
    webhook_secret = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

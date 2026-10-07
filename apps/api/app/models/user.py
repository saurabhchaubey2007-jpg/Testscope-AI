from sqlalchemy import Column, String, DateTime
from datetime import datetime
import uuid
from apps.api.app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    github_token = Column(String, nullable=True)
    llm_provider = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

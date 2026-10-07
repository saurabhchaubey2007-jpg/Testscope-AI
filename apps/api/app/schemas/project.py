from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from typing import Optional, List, Literal


class ProjectCreate(BaseModel):
    name: str
    source_type: Literal["local", "github"] = "local"
    # Required for local projects
    repository_path: Optional[str] = None
    # Required for GitHub projects
    repo_url: Optional[str] = None
    default_branch: Optional[str] = None
    test_types: List[Literal["unit", "e2e"]] = Field(default_factory=lambda: ["unit"])
    app_url: Optional[str] = None

    @model_validator(mode="after")
    def check_source(self):
        if self.source_type == "local" and not self.repository_path:
            raise ValueError("repository_path is required for local projects")
        if self.source_type == "github" and not self.repo_url:
            raise ValueError("repo_url is required for GitHub projects")
        if "e2e" in self.test_types and not self.app_url:
            raise ValueError("app_url is required when E2E tests are enabled")
        if not self.test_types:
            raise ValueError("At least one test type must be selected")
        return self


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    default_branch: Optional[str] = None
    test_types: Optional[List[Literal["unit", "e2e"]]] = None
    app_url: Optional[str] = None


class ProjectOut(BaseModel):
    id: str
    name: str
    repository_path: Optional[str] = None
    source_type: str = "local"
    repo_url: Optional[str] = None
    default_branch: Optional[str] = None
    test_types: List[str] = Field(default_factory=lambda: ["unit"])
    app_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectDetailOut(ProjectOut):
    webhook_secret: Optional[str] = None
    run_count: int = 0
    last_run_status: Optional[str] = None
    last_run_at: Optional[datetime] = None

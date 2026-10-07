import pytest
from fastapi.testclient import TestClient
from apps.api.app.main import app
from apps.api.app.core.database import Base, get_db
import os
from apps.api.app.models.project import Project
from apps.api.app.models.run import Run
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:////data/TestscopeAI/test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("/tmp/test.db"):
        os.remove("/tmp/test.db")

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

def test_create_project():
    response = client.post("/api/v1/projects/", json={
        "name": "Sample Project",
        "repository_path": "./workspace/repositories/sample_app"
    })
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["name"] == "Sample Project"
    
    return data["id"]

def test_create_run(monkeypatch):
    monkeypatch.setenv("USE_FAKE_LLM", "true")
    project_id = test_create_project()
    repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../workspace/repositories/sample_app"))
    
    response = client.post(f"/api/v1/projects/{project_id}/runs", json={
        "repository_path": repo_path
    })
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    
    run_id = data["id"]
    
    # Get run
    response = client.get(f"/api/v1/runs/{run_id}")
    assert response.status_code == 200
    
    # Get report
    response = client.get(f"/api/v1/runs/{run_id}/report")
    assert response.status_code == 200
    report_data = response.json()
    assert "summary" in report_data

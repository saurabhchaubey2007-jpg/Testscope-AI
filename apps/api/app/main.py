from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.api.app.api.routes import projects, runs
from apps.api.app.core.database import Base, engine

app = FastAPI(title="TestScope AI - Phase 1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For MVP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)

app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(runs.router, prefix="/api/v1/runs", tags=["runs"])

@app.get("/health")
def health_check():
    return {"status": "ok"}

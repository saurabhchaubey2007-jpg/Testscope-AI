import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.api.routes import auth, projects, runs, webhooks
from apps.api.app.core.config import settings
from apps.api.app.core.database import Base, engine
import apps.api.app.models  # noqa: F401  (register all tables)

logging.basicConfig(level=logging.INFO)

ROOT_DIR = str(Path(__file__).resolve().parents[3])


def run_migrations() -> None:
    """Apply Alembic migrations; fall back to create_all if Alembic isn't configured."""
    ini_path = os.path.join(ROOT_DIR, "alembic.ini")
    if not os.path.exists(ini_path):
        Base.metadata.create_all(bind=engine)
        return
    from alembic import command
    from alembic.config import Config

    cfg = Config(ini_path)
    cfg.set_main_option("script_location", os.path.join(ROOT_DIR, "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("TESTSCOPE_SKIP_MIGRATIONS") != "true":
        run_migrations()
    from apps.api.app.services.run_worker import recover_stale_runs
    recover_stale_runs()
    yield


app = FastAPI(title="TestScope AI", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(runs.router, prefix="/api/v1/runs", tags=["runs"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"name": "TestScope AI API", "docs": "/docs", "health": "/health"}

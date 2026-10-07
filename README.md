# TestScope AI - Phase 1

This is Phase 1 of the TestScope AI autonomous testing agent. It proves the core loop locally.

## Prerequisites
- Python 3.11+
- Docker and docker-compose (for PostgreSQL)

## Installation

1. Copy `.env.example` to `.env`
2. Run `make install`

## Starting PostgreSQL

`make db-up`

## Environment Variables

Edit `.env`:
- `DATABASE_URL`: Connection string to PostgreSQL
- `WORKSPACE_DIR`: Directory containing your local repos (e.g. `./workspace`)
- `DEFAULT_LLM_PROVIDER`: `gemini` or `groq` (or use `USE_FAKE_LLM=true` for testing)
- `GOOGLE_API_KEY` / `GROQ_API_KEY`: API keys for the respective providers

## Running the API

`make dev`

This will start the FastAPI server on port 8000.

## Running Tests

`make test`

## Usage (API)

1. Create a project:
   `POST /api/v1/projects`
   `{"name": "test", "repository_path": "/path/to/repo"}`
   
2. Start a run:
   `POST /api/v1/projects/{project_id}/runs`
   `{"repository_path": "/path/to/repo"}`
   
3. Get the run report:
   `GET /api/v1/runs/{run_id}/report`

## Intentionally Deferred Features

- MCP
- GitHub App/webhooks
- Redis
- pgvector/RAG
- Docker sandbox
- Playwright/Selenium
- OpenTelemetry/Prometheus/Grafana
- LangSmith
- MinIO/S3
- distributed workers
- complex auth/RBAC
- production deployment
- advanced approvals
- semantic cache
- production model quota/fallback system

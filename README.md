# TestScope AI — Phase 2

TestScope turns a repository into a test plan, generates Python tests, runs them, classifies failures, and repairs test defects up to three times per phase. It supports local repositories, GitHub projects, and browser tests against an already running application.

## Local setup

Requirements: Python 3.11+, Node.js 20.9+, Git. Docker is optional (PostgreSQL only).

```bash
cp .env.example .env
make install
make playwright
cd apps/web
npm ci
cp .env.example .env.local
```

Set a random `JWT_SECRET` of at least 32 characters and your provider API key in the root `.env`. Model IDs can be overridden with `GEMINI_MODEL` and `GROQ_MODEL`; defaults were checked against [Google’s model catalog](https://ai.google.dev/gemini-api/docs/models) and [Groq’s supported models](https://console.groq.com/docs/models). `DATABASE_URL` defaults to SQLite. To use PostgreSQL, run `make db-up` and set `DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/testscope`.

Start the API from the repository root with `make dev` (port 8000), and the frontend in another terminal with `make web` (port 3000). Open http://localhost:3000 and register an account. API docs are at http://localhost:8000/docs.

For an offline workflow check, start the API with `USE_FAKE_LLM=true make dev`. Fake mode generates a trivial unit smoke test and a homepage browser test; it does **not** assess application correctness. Real generation requires provider credentials.

The API applies Alembic migrations on startup. Existing versioned Phase 2 databases upgrade automatically. Back up an older unversioned Phase 1 database before migrating it; the initial migration expects an empty database. Do not delete an existing database to resolve a schema error.

## Dashboard

- `/login`, `/register`: JWT authentication through an httpOnly cookie.
- `/projects`: searchable projects and recent runs.
- `/projects/new`: local path or GitHub URL, unit tests, browser tests, or both.
- `/projects/[id]`: overview, run history, branch override, webhook setup, and deletion.
- `/runs/[id]`: live progress, cancellation, structured test inventory, generated code, stdout/stderr, failure evidence, repairs, screenshots and traces.
- `/settings`: profile, GitHub personal access token, and per-user LLM provider.

Browser API calls use `NEXT_PUBLIC_API_URL`, defaulting to `/api/backend`. Next.js route handlers forward requests to `API_INTERNAL_URL` (default `http://127.0.0.1:8000/api/v1`), forward the httpOnly session cookie, and remove access tokens from login/register responses. The server enforces ownership for projects, runs, reports, events, and artifacts. `COOKIE_SECURE=true` is required when serving over HTTPS. No token is kept in localStorage.

## GitHub

Create a GitHub project with `https://github.com/<owner>/<repo>`. The worker shallow-clones into `workspace/repositories/<project_id>`. Add a per-user PAT in Settings for private repositories and PR comments. Git credentials are passed through temporary process configuration, never included in clone URLs.

On the project page, copy the webhook URL and per-project secret into GitHub → repository Settings → Webhooks. Choose `application/json` and subscribe to Pull requests and Pushes. Supported PR actions: opened, synchronize, reopened, ready_for_review (drafts are ignored). Pushes to the configured/default branch also queue runs. HMAC signatures are required. Runs record the branch, PR number, and commit SHA; queued PR runs check out the recorded SHA.

For local webhook delivery, point a public tunnel (for example ngrok) at the API port and set `NEXT_PUBLIC_WEBHOOK_BASE_URL` in `apps/web/.env.local` to that HTTPS origin. This URL is displayed by the dashboard; GitHub webhooks go directly to the API. Creating a tunnel and configuring a real repository are manual setup steps. Runs on PRs post a summary comment when the project owner has saved a PAT with the necessary permission.

## Browser tests

Enable E2E and supply an `http://` or `https://` application URL reachable from the backend. TestScope does not start the target application or install its dependencies. Install those dependencies separately. The E2E branch generates Python `pytest-playwright` tests and uses Chromium. Failure screenshots and traces are saved under `workspace/artifacts/<run_id>` and linked from the run report.

Test execution uses the API Python environment with the repository root in `PYTHONPATH`. Generated tests execute with local process permissions; Phase 2 is intended for trusted repositories in a local environment. Container isolation, a durable distributed queue, rate limits, and token encryption at rest remain future work. GitHub tokens currently reside in the database: restrict database access. Use a single API process; startup recovery marks interrupted runs failed, and project locks are process-local. Cancellation is cooperative between graph nodes, so the current LLM call/test may finish first.

## Verification

```bash
make test
cd apps/web
npm run lint
npm run build
```

If Turbopack cannot bind a build-worker port in a restricted environment, use `npm run build -- --webpack`. The backend tests use a temporary SQLite database and fake LLM; they do not require provider credentials or a real GitHub repository. They cover auth and ownership, queued cancellation, migrations, structured pytest counts, generated filename validation, E2E routing, and Git checkout behavior.

The current pipeline is Python-first for unit tests; bounded Python/JS/TS/template source context also informs browser test planning. Model-generated tests and failure classifications require review. A `COMPLETED` run means the pipeline finished, including when its report contains failing tests.

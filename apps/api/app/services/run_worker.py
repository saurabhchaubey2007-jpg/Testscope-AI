"""Background execution of test runs.

Runs are executed on a small thread pool so the API returns immediately.
Runs belonging to the same project are serialised with a per-project lock,
because they share the same working copy on disk.
"""
import logging
import threading
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from apps.api.app.core.config import settings
from apps.api.app.core.database import SessionLocal
from apps.api.app.models.project import Project
from apps.api.app.models.run import Run
from apps.api.app.models.user import User
from apps.api.app.services import git_service
from apps.api.app.services.run_events import record_event, RunCancelled

logger = logging.getLogger("testscope.worker")

_executor = ThreadPoolExecutor(max_workers=max(1, settings.max_concurrent_runs), thread_name_prefix="run-worker")
_project_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
_locks_guard = threading.Lock()

# Tests can set this to True to execute runs inline (deterministic, no threads)
RUN_INLINE = False


def _lock_for(project_id: str) -> threading.Lock:
    with _locks_guard:
        return _project_locks[project_id]


def enqueue_run(run_id: str, repository_path: str | None = None) -> None:
    if RUN_INLINE:
        execute_run(run_id, repository_path)
    else:
        _executor.submit(execute_run, run_id, repository_path)


def execute_run(run_id: str, repository_path: str | None = None) -> None:
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run or run.status == "CANCELLED":
            return
        project = db.query(Project).filter(Project.id == run.project_id).first()
        owner = db.query(User).filter(User.id == project.owner_id).first() if project and project.owner_id else None
        if not project:
            run.status = "FAILED"
            run.status_reason = "Project not found"
            db.commit()
            return

        with _lock_for(project.id):
            db.refresh(run)
            if run.status == "CANCELLED":
                return
            run.status = "RUNNING"
            run.started_at = datetime.utcnow()
            db.commit()

            try:
                repo_path = repository_path or project.repository_path

                if project.source_type == "github":
                    record_event(run_id, "step_started", "checkout")
                    sha = git_service.checkout(
                        project.repo_url,
                        git_service.clone_dir_for(project.id),
                        ref=run.commit_sha or run.branch or project.default_branch,
                        pr_number=run.pr_number,
                        token=owner.github_token if owner else None,
                    )
                    repo_path = git_service.clone_dir_for(project.id)
                    run.commit_sha = sha
                    db.commit()
                    record_event(run_id, "step_finished", "checkout", f"Checked out {sha[:7]}")

                from apps.api.app.services.report_service import run_pipeline, save_results
                from packages.llm_router.router import active_provider
                provider_token = active_provider.set(owner.llm_provider if owner else None)
                try:
                    final_state = run_pipeline(run_id, project, repo_path)
                finally:
                    active_provider.reset(provider_token)
                save_results(run_id, final_state, db)

                db.refresh(run)
                if run.status != "CANCELLED":
                    run.status = "COMPLETED"
            except RunCancelled:
                run.status = "CANCELLED"
                record_event(run_id, "log", message="Run cancelled by user")
            except Exception as e:  # noqa: BLE001
                logger.exception("Run %s failed", run_id)
                db.rollback()
                run = db.query(Run).filter(Run.id == run_id).first()
                run.status = "FAILED"
                run.status_reason = str(e)[:2000]
                record_event(run_id, "error", message=traceback.format_exc()[-4000:])

            run.current_step = None
            run.finished_at = datetime.utcnow()
            db.commit()

        _maybe_comment_on_pr(run, project, owner)
    finally:
        db.close()


def _maybe_comment_on_pr(run: Run, project: Project, owner: User | None) -> None:
    if not (run.pr_number and project.source_type == "github" and owner and owner.github_token):
        return
    s = run.summary or {}
    icon = {"COMPLETED": "✅", "FAILED": "❌", "CANCELLED": "⚪"}.get(run.status, "ℹ️")
    body = (
        f"### {icon} TestScope AI run {run.status.lower()}\n\n"
        f"| Generated | Passed | Failed | Repaired |\n|---|---|---|---|\n"
        f"| {s.get('generated', 0)} | {s.get('passed', 0)} | {s.get('failed', 0)} | {s.get('repaired', 0)} |\n\n"
        f"Commit: `{(run.commit_sha or '')[:7]}` · Run ID: `{run.id}`"
    )
    if run.status_reason:
        body += f"\n\n> {run.status_reason[:500]}"
    try:
        git_service.post_pr_comment(project.repo_url, run.pr_number, owner.github_token, body)
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to post PR comment for run %s: %s", run.id, e)


def recover_stale_runs() -> None:
    """Runs left RUNNING/QUEUED when the server stopped can never finish; mark them failed."""
    db = SessionLocal()
    try:
        stale = db.query(Run).filter(Run.status.in_(["RUNNING", "QUEUED"])).all()
        for run in stale:
            run.status = "FAILED"
            run.status_reason = "Server restarted while the run was in progress"
            run.current_step = None
            run.finished_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()

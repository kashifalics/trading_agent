"""Background job dispatch. JOB_BACKEND=inline runs jobs in FastAPI's thread pool (default, no Redis needed);
JOB_BACKEND=celery sends them to the Celery worker (docker compose `worker` service)."""
import logging
from collections.abc import Callable

from fastapi import BackgroundTasks

from app.core.config import get_settings
from app.opportunities.scanner import run_scan_job
from app.services.analysis_service import run_analysis_job
from app.services.backtest_service import run_backtest_job
from app.services.model_service import train_model_job

log = logging.getLogger(__name__)

JOBS: dict[str, Callable] = {
    "analysis": run_analysis_job,
    "backtest": run_backtest_job,
    "train_model": train_model_job,
    "scan": run_scan_job,
}


def dispatch(name: str, background: BackgroundTasks, *args) -> None:
    """Send the job to Celery when configured. If the broker cannot take it (Redis down, incompatible client libraries), the job
    runs inline instead of failing the request and leaving its row 'queued' forever (which also blocked later scans as duplicates)."""
    s = get_settings()
    if s.job_backend == "celery" and s.redis_url:
        try:
            from app.jobs.worker import celery_app

            celery_app.send_task(f"ati.{name}", args=list(args))
            return
        except Exception as exc:  # noqa: BLE001 - any broker failure falls back to inline execution
            log.warning("celery dispatch of %s failed (%s: %s); running it inline", name, exc.__class__.__name__, str(exc)[:200])
    background.add_task(JOBS[name], *args)

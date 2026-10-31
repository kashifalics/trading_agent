"""Background job dispatch. JOB_BACKEND=inline runs jobs in FastAPI's thread pool (default, no Redis needed);
JOB_BACKEND=celery sends them to the Celery worker (docker compose `worker` service)."""
from collections.abc import Callable

from fastapi import BackgroundTasks

from app.core.config import get_settings
from app.services.analysis_service import run_analysis_job
from app.services.backtest_service import run_backtest_job
from app.services.model_service import train_model_job

JOBS: dict[str, Callable] = {
    "analysis": run_analysis_job,
    "backtest": run_backtest_job,
    "train_model": train_model_job,
}


def dispatch(name: str, background: BackgroundTasks, *args) -> None:
    s = get_settings()
    if s.job_backend == "celery" and s.redis_url:
        from app.jobs.worker import celery_app

        celery_app.send_task(f"ati.{name}", args=list(args))
    else:
        background.add_task(JOBS[name], *args)

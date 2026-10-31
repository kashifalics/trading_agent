from celery import Celery

from app.core.config import get_settings

_s = get_settings()
celery_app = Celery("ati", broker=_s.redis_url or "memory://", backend=_s.redis_url or "cache+memory://")
celery_app.conf.update(task_serializer="json", accept_content=["json"], task_acks_late=True,
                       worker_prefetch_multiplier=1, task_time_limit=3600)


@celery_app.task(name="ati.analysis")
def analysis_task(analysis_id: int) -> None:
    from app.services.analysis_service import run_analysis_job

    run_analysis_job(analysis_id)


@celery_app.task(name="ati.backtest")
def backtest_task(run_id: int) -> None:
    from app.services.backtest_service import run_backtest_job

    run_backtest_job(run_id)


@celery_app.task(name="ati.train_model")
def train_model_task(params: dict) -> None:
    from app.services.model_service import train_model_job

    train_model_job(params)

import logging
from pathlib import Path

from sqlalchemy import inspect

from app.core.config import get_settings
from app.database.base import Base
from app.database.models import *  # noqa: F401,F403 - register tables
from app.database.session import get_engine, session_scope
from app.market_data.ingestion.service import seed_reference_data

log = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[2]


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


def init_db() -> None:
    """Migrate (Alembic) on file/server databases, create_all on in-memory test databases, then seed reference data."""
    s = get_settings()
    engine = get_engine()
    in_memory = engine.url.get_backend_name() == "sqlite" and engine.url.database in (None, "", ":memory:")
    if in_memory or not s.auto_migrate:
        if in_memory:
            Base.metadata.create_all(engine)
    else:
        run_migrations()
    if not inspect(engine).has_table("instruments"):
        log.warning("database schema missing; run `alembic upgrade head`")
        return
    with session_scope() as session:
        seed_reference_data(session)
        from app.core.security import ensure_bootstrap_user

        if ensure_bootstrap_user(session):
            log.info("owner API key from BOOTSTRAP_API_KEY is active")

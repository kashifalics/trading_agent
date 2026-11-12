import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ["PREFERRED_PROVIDER"] = ""  # legacy tests assert status-based routing; preference has its own tests
os.environ["TWELVE_DATA_API_KEY"] = ""  # unit tests must never reach a real provider, whatever .env contains
os.environ["PAPER_TRADING_INTERVAL_SECONDS"] = "0"  # no background paper-trading loop (it would sync from real providers)
os.environ["OPPORTUNITY_SCAN_INTERVAL_MINUTES"] = "0"  # no scheduled opportunity scan either
os.environ.setdefault("MODEL_DIR", "./.test_model_store")
os.environ.setdefault("UPLOAD_DIR", "./.test_uploads")

from datetime import datetime, timedelta, timezone  # noqa: E402
from decimal import Decimal  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import String, event  # noqa: E402
from sqlalchemy import inspect as sa_inspect  # noqa: E402
from sqlalchemy.orm import Session as OrmSession  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database.base import Base  # noqa: E402
from app.database.models import *  # noqa: E402,F401,F403
from app.database.session import make_engine, set_engine  # noqa: E402
from app.market_data.ingestion.service import seed_reference_data  # noqa: E402
from app.market_data.types import Candle  # noqa: E402


@event.listens_for(OrmSession, "before_flush")
def _enforce_declared_string_lengths(session, flush_context, instances):
    """SQLite ignores VARCHAR(n) but PostgreSQL rejects longer values. Enforce every declared length in the tests, so a value that
    would fail on PostgreSQL (as 'insufficient_data' in VARCHAR(16) once did, breaking every scan there) fails here too."""
    for obj in list(session.new) + list(session.dirty):
        mapper = sa_inspect(obj).mapper
        for col in mapper.columns:
            if isinstance(col.type, String) and col.type.length:
                v = getattr(obj, mapper.get_property_by_column(col).key, None)
                if isinstance(v, str) and len(v) > col.type.length:
                    raise AssertionError(f"{mapper.class_.__name__}.{col.key} = {v!r} has {len(v)} characters; the column allows "
                                         f"{col.type.length} (PostgreSQL would reject it)")


@pytest.fixture(autouse=True)
def _fresh_signal_summary():
    """Each test gets its own database, so the in-memory signal summary from an earlier test must not be reused."""
    from app.signals import service as signal_service
    signal_service._ITEMS.clear()
    signal_service._FULL.clear()
    yield
    signal_service._ITEMS.clear()
    signal_service._FULL.clear()


@pytest.fixture()
def engine():
    eng = make_engine("sqlite://")
    Base.metadata.create_all(eng)
    set_engine(eng)
    return eng


@pytest.fixture()
def session(engine):
    with sessionmaker(engine, expire_on_commit=False)() as s:
        seed_reference_data(s)
        yield s


def make_candles(n: int, start: datetime, step_s: int = 3600, base: float = 100.0, seed: int = 1,
                 drift: float = 0.0, vol: float = 0.5) -> list[Candle]:
    """Deterministic synthetic candles. TEST FIXTURES ONLY - never shown as market data."""
    rng = np.random.default_rng(seed)
    price, out = base, []
    for i in range(n):
        o = price
        c = o + drift + rng.normal(0, vol)
        h = max(o, c) + abs(rng.normal(0, vol / 2))
        lo = min(o, c) - abs(rng.normal(0, vol / 2))
        out.append(Candle(ts=start + timedelta(seconds=i * step_s), open=Decimal(str(round(o, 4))),
                          high=Decimal(str(round(h, 4))), low=Decimal(str(round(lo, 4))),
                          close=Decimal(str(round(c, 4))), volume=Decimal("10"), volume_type="base"))
        price = c
    return out


UTC0 = datetime(2024, 1, 1, tzinfo=timezone.utc)

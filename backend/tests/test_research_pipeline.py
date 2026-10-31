from datetime import datetime, timedelta, timezone
from decimal import Decimal

import numpy as np
import pytest
from sqlalchemy import func, select

from app.core.exceptions import ProviderError
from app.database.models import Candle as CandleRow
from app.database.models import Experiment
from app.market_data.bars import Bars
from app.market_data.base import MarketDataProvider
from app.market_data.ingestion.backfill import backfill_candles, expected_open_times
from app.market_data.ingestion.service import anchor_for, resolve_mapping, store_candles
from app.market_data.timeframes import get_timeframe
from app.market_data.types import Candle
from app.research.data_quality import compute_quality, render_markdown
from app.research.experiments import code_version, dataset_snapshot, record_experiment
from app.research.reproduce import compare, reproduce
from app.research.strategy_eval import (
    buy_and_hold,
    run_backtest_experiment,
    significance,
    sma_trend_long_flat,
    verdict,
)
from tests.conftest import make_candles

NOW = datetime(2024, 6, 1, 12, 30, tzinfo=timezone.utc)  # forming candle opens 12:00
START = datetime(2024, 5, 20, 0, 0, tzinfo=timezone.utc)
H = timedelta(hours=1)


class FakeBinance(MarketDataProvider):
    """Deterministic provider over a synthetic series with injectable faults. TEST ONLY."""

    code = "fake"
    native_timeframes = {"1H": "1h", "4H": "4h"}

    def __init__(self, first=None, holes=(), fail_on_call=None, bad=None):
        series = make_candles(24 * 20, START - timedelta(days=0), 3600, base=60000, seed=5, vol=40)
        self.data = {c.ts: c for c in series}
        self.first = first
        self.holes = set(holes)
        self.fail_on_call = fail_on_call
        self.bad = bad or {}
        self.calls: list[tuple[datetime, datetime]] = []

    def is_configured(self): return True
    def get_instruments(self, symbols=None): return []
    def get_latest_quote(self, symbol): raise NotImplementedError
    def get_market_status(self, symbol): return {}
    def get_provider_metadata(self): raise NotImplementedError
    def check_data_coverage(self, symbol, timeframe): return {}

    def get_candles(self, symbol, timeframe, start=None, end=None, limit=None):
        self.calls.append((start, end))
        if self.fail_on_call is not None and len(self.calls) == self.fail_on_call:
            raise ProviderError("simulated outage")
        out = []
        for ts, c in sorted(self.data.items()):
            if start <= ts <= end and ts not in self.holes and (self.first is None or ts >= self.first):
                out.append(self.bad.get(ts, c))
        return out


def setup(session, provider=None):
    inst, prov, pi = resolve_mapping(session, "BTCUSDT", "binance")
    return inst, prov, pi, provider or FakeBinance()


def n_rows(session):
    return session.scalar(select(func.count()).select_from(CandleRow))


def test_backfill_complete_then_idempotent(session):
    inst, prov, pi, fake = setup(session)
    run = backfill_candles(session, fake, inst, prov, pi, "1H", START, now=NOW, window_candles=100)
    expected = len(expected_open_times(get_timeframe("1H"), START, datetime(2024, 6, 1, 12, tzinfo=timezone.utc), anchor_for(inst)))
    assert run.status == "completed" and run.missing_before == expected and run.missing_after == 0
    assert n_rows(session) == expected == run.stored and run.requests >= 3
    calls = len(fake.calls)
    again = backfill_candles(session, fake, inst, prov, pi, "1H", START, now=NOW, window_candles=100)
    assert again.status == "completed" and again.requests == 0 and again.stored == 0 and len(fake.calls) == calls
    assert n_rows(session) == expected


def test_backfill_never_stores_the_forming_candle(session):
    inst, prov, pi, fake = setup(session)
    backfill_candles(session, fake, inst, prov, pi, "1H", START, now=NOW, window_candles=500)
    last = session.scalar(select(func.max(CandleRow.ts)))
    assert last == datetime(2024, 6, 1, 11, tzinfo=timezone.utc)  # 12:00 candle is still forming at 12:30


def test_backfill_is_resumable_after_failure_and_refetches_only_what_is_missing(session):
    inst, prov, pi, _ = setup(session)
    flaky = FakeBinance(fail_on_call=3)
    with pytest.raises(ProviderError):
        backfill_candles(session, flaky, inst, prov, pi, "1H", START, now=NOW, window_candles=100)
    from app.database.models import IngestionRun
    run1 = session.scalars(select(IngestionRun).order_by(IngestionRun.id)).first()
    assert run1.status == "partial" and "simulated outage" in run1.error
    stored_after_failure = n_rows(session)
    assert stored_after_failure == 200  # two committed windows survived the crash
    healthy = FakeBinance()
    run2 = backfill_candles(session, healthy, inst, prov, pi, "1H", START, now=NOW, window_candles=100)
    assert run2.status == "completed" and run2.missing_before == run2.stored  # exactly the missing part was fetched
    assert min(c[0] for c in healthy.calls) >= START + 200 * H  # first two windows were NOT requested again
    assert n_rows(session) == stored_after_failure + run2.stored


def test_backfill_validates_and_reports_bad_data_without_repairing_it(session):
    bad_ts = START + 10 * H
    broken = Candle(bad_ts, Decimal(10), Decimal(9), Decimal(11), Decimal(10))  # high < low
    inst, prov, pi, _ = setup(session)
    fake = FakeBinance(bad={bad_ts: broken, START + 20 * H: Candle(START + 20 * H + timedelta(minutes=17), Decimal(1), Decimal(2), Decimal(1), Decimal(1))})
    run = backfill_candles(session, fake, inst, prov, pi, "1H", START, now=NOW, window_candles=500)
    assert run.rejected == 1 and run.misaligned == 1
    assert run.missing_after == 2 and run.status == "partial"  # both slots stay missing: nothing was invented
    assert session.scalar(select(func.count()).select_from(CandleRow).where(CandleRow.ts == bad_ts)) == 0


def test_permanent_hole_is_a_reported_gap_while_pre_listing_history_is_not(session):
    inst, prov, pi, _ = setup(session)
    hole = START + 50 * H
    fake = FakeBinance(first=START + 5 * H, holes=[hole])
    run = backfill_candles(session, fake, inst, prov, pi, "1H", START, now=NOW, window_candles=500)
    assert run.missing_after == 1 and run.meta["pre_history_unavailable"] == 5 and run.status == "partial"
    q = compute_quality(session, inst, prov, "1H", NOW)
    assert q["missing_count"] == 1 and q["gaps"][0]["start"] == hole.isoformat() and q["coverage_pct"] < 100
    assert q["status"] == "issues found" and q["first_candle"] == (START + 5 * H).isoformat()
    md = render_markdown([q])
    assert hole.date().isoformat() in md and "Coverage %" in md


def test_expected_open_times_respect_market_calendar():
    tf = get_timeframe("1H")
    start, end = datetime(2024, 1, 5, 20, tzinfo=timezone.utc), datetime(2024, 1, 8, 4, tzinfo=timezone.utc)
    from app.market_data.timeframes import UTC_ANCHOR
    cont = expected_open_times(tf, start, end, UTC_ANCHOR, "continuous")
    fx = expected_open_times(tf, start, end, UTC_ANCHOR, "fx_weekly")
    assert len(cont) == 56 and len(fx) == 2 + 6  # Fri 20,21 UTC open; closed until Sun 22:00 UTC; then 22,23,00,01,02,03


def test_quality_audit_detects_corruption_independently_of_ingestion(session):
    inst, prov, pi, fake = setup(session)
    backfill_candles(session, fake, inst, prov, pi, "1H", START, now=NOW, window_candles=500)
    # simulate later corruption directly in the database
    victim = session.scalars(select(CandleRow).where(CandleRow.ts == START + 7 * H)).one()
    victim.high = Decimal("1")  # high below open/close
    gone = session.scalars(select(CandleRow).where(CandleRow.ts == START + 30 * H)).one()
    session.delete(gone)
    session.add(CandleRow(instrument_id=inst.id, provider_id=prov.id, timeframe="1H", ts=START + 40 * H + timedelta(minutes=5),
                          open=Decimal(5), high=Decimal(6), low=Decimal(4), close=Decimal(5), volume=Decimal(1), is_complete=True))
    session.commit()
    q = compute_quality(session, inst, prov, "1H", NOW)
    assert q["invalid_stored"] == 1 and q["misaligned_stored"] == 1
    assert q["missing_count"] == 1 and q["gaps"][0]["start"] == (START + 30 * H).isoformat()  # off-grid row fills no slot
    assert q["status"] == "issues found"


def test_snapshot_id_is_content_addressed(session):
    inst, prov, pi, fake = setup(session)
    backfill_candles(session, fake, inst, prov, pi, "1H", START, now=NOW, window_candles=500)
    a = dataset_snapshot(session, inst.id, prov.id, "1H", "BTCUSDT", "binance")
    assert a == dataset_snapshot(session, inst.id, prov.id, "1H", "BTCUSDT", "binance") and a["n_candles"] > 200
    row = session.scalars(select(CandleRow).order_by(CandleRow.ts).limit(1)).one()
    row.close = row.close + Decimal("0.01")
    session.commit()
    assert dataset_snapshot(session, inst.id, prov.id, "1H", "BTCUSDT", "binance")["snapshot_id"] != a["snapshot_id"]
    sub = dataset_snapshot(session, inst.id, prov.id, "1H", "BTCUSDT", "binance", end=START + 100 * H)
    assert sub["n_candles"] == 101 and sub["snapshot_id"] != a["snapshot_id"]


def synthetic_series(session, n=500, seed=8):
    inst, prov, pi = resolve_mapping(session, "BTCUSDT", "binance")
    store_candles(session, inst.id, prov.id, "1H", make_candles(n, START, 3600, base=60000, seed=seed, vol=120, drift=3))
    return inst, prov


SPEC = {"symbol": "BTCUSDT", "provider": "binance", "timeframe": "1H", "strategy": "ma_cross", "strategy_params": {},
        "cost_scenario": "base", "backtest": {"risk_pct": 1.0, "max_bars_in_trade": 100, "eval_every": 1}, "n_folds": 3}


def test_experiment_round_trip_and_reproduction(session):
    inst, prov = synthetic_series(session)
    res, snap = run_backtest_experiment(session, SPEC)
    assert res["n_trades"] > 5 and {"folds", "by_regime", "significance", "verdict", "by_direction"} <= set(res)
    e = record_experiment(session, "backtest", "bt:test", snap, {"spec": {**SPEC, "expected_snapshot": snap["snapshot_id"]}}, res, 1.0)
    assert e.code_version["source_sha256"] and "numpy" in e.code_version["libs"]
    out = reproduce(e.id)
    assert out["reproduced"] and out["snapshot_matches"] and out["code_hash_matches"] and out["numeric_fields_compared"] > 10
    assert code_version()["source_sha256"] == e.code_version["source_sha256"]
    # different cost scenario => different results (the comparison is not vacuous)
    other, _ = run_backtest_experiment(session, {**SPEC, "cost_scenario": "zero_cost"})
    assert compare(res, other)


def test_reproduction_refuses_when_the_dataset_changed(session):
    inst, prov = synthetic_series(session)
    res, snap = run_backtest_experiment(session, SPEC)
    e = record_experiment(session, "backtest", "bt:test", snap, {"spec": {**SPEC, "expected_snapshot": snap["snapshot_id"]}}, res)
    row = session.scalars(select(CandleRow).order_by(CandleRow.ts.desc()).limit(1)).one()
    row.high = row.high + Decimal(5)
    session.commit()
    with pytest.raises(ValueError, match="dataset changed"):
        reproduce(e.id)
    assert session.get(Experiment, e.id).results["n_trades"] == res["n_trades"]  # stored result untouched


def test_baselines_and_verdict_logic():
    n = 600
    c = 100 * np.exp(np.cumsum(np.full(n, 0.002)))  # steady uptrend
    up = Bars.from_arrays(c, c * 1.001, c * 0.999, c, step=3600)
    zero, base = buy_and_hold(up, 120, "zero_cost"), buy_and_hold(up, 120, "base")
    assert zero["total_return_pct"] > base["total_return_pct"] > 0 and zero["max_drawdown_pct"] < 1
    trend = sma_trend_long_flat(up, 120, "base")
    assert trend["n_trades"] == 1 and 0 < trend["total_return_pct"] <= zero["total_return_pct"]
    rng = np.random.default_rng(0)
    assert verdict(significance(rng.normal(0.30, 1, 400)), 0.83, 400).startswith("POSITIVE")
    assert verdict(significance(rng.normal(-0.30, 1, 400)), 0.2, 400).startswith("NEGATIVE")
    assert verdict(significance(rng.normal(0.0, 1, 400)), 0.5, 400).startswith("NO EVIDENCE")
    assert verdict(significance(rng.normal(0.5, 1, 40)), 1.0, 40).startswith("INSUFFICIENT")
    assert verdict(significance(rng.normal(0.30, 1, 400)), 0.5, 400).startswith("NO EVIDENCE")  # unstable across folds


def test_many_unfillable_holes_cost_few_requests_on_a_resumed_run(session):
    inst, prov, pi, _ = setup(session)
    holes = [START + h * H for h in range(5, 290, 7)]  # ~41 permanent holes, like maintenance breaks
    fake = FakeBinance(holes=holes)
    backfill_candles(session, fake, inst, prov, pi, "1H", START, now=NOW, window_candles=100)
    first_requests = len(fake.calls)
    again = FakeBinance(holes=holes)
    run = backfill_candles(session, again, inst, prov, pi, "1H", START, now=NOW, window_candles=100)
    assert run.missing_before == len(holes) and run.missing_after == len(holes)
    assert len(again.calls) <= 5 < len(holes)  # span-based windows, not one request per hole
    assert first_requests >= len(again.calls)

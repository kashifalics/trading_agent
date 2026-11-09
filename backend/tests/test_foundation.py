"""Phase 0 data foundation on synthetic Dukascopy files (TEST FIXTURES ONLY, never market data): timeframe rebuild verified
against direct M1 aggregation, timeframe sync without leakage, frozen split, sealed loader, M1 store, quality report."""
import json
import lzma
from datetime import date, datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest

from app.historical import build as B
from app.historical import download as D
from app.historical import quality as Q
from app.historical import reference as R
from app.historical import split as Sp
from app.historical import store as St
from app.historical import sync as Sy
from app.historical.dukascopy import RECORD


def bi5(rows, point=1e-3) -> bytes:
    raw = b"".join(RECORD.pack(t, round(o / point), round(c / point), round(lo / point), round(h / point), v) for t, o, h, lo, c, v in rows)
    return lzma.compress(raw, format=lzma.FORMAT_ALONE)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    for mod in (B, D, Q):
        monkeypatch.setattr(mod, "RAW", tmp_path / "raw")
    for name in ("NORMALIZED", "CLEAN", "REPORTS"):
        for mod in (B, Q, R, Sp, St):
            if hasattr(mod, name):
                monkeypatch.setattr(mod, name, tmp_path / name.lower())
    monkeypatch.setattr(St, "DATA_ROOT", tmp_path)
    for mod in (Sp, St):
        monkeypatch.setattr(mod, "SPLIT_DIR", tmp_path / "research")
    monkeypatch.setattr(Q, "REPO_ROOT", tmp_path / "repo")
    (tmp_path / "repo" / "docs" / "reports").mkdir(parents=True)
    return tmp_path


def write_days(start: date, days: int, seed: int = 3):
    """Gold-like synthetic minutes for `days` calendar days (Saturdays skipped like the downloader), bid and ask."""
    rng = np.random.default_rng(seed)
    p = 1800.0
    for k in range(days):
        d = start + timedelta(days=k)
        if d.weekday() == 5:
            continue
        rows = {"BID": [], "ASK": []}
        for m in range(1440):
            o = p
            p = max(1.0, p + rng.normal(0, 0.2))
            hi, lo = max(o, p) + rng.uniform(0, 0.1), min(o, p) - rng.uniform(0, 0.1)
            for side, off in (("BID", 0.0), ("ASK", 0.3)):
                rows[side].append((m * 60, o + off, hi + off, lo + off, p + off, 1.0 + rng.uniform()))
        for side in ("BID", "ASK"):
            path = D.raw_path("XAUUSD", side, d)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(bi5(rows[side]))


def test_every_timeframe_is_identical_to_direct_m1_aggregation_and_ny_days_follow_dst(store):
    write_days(date(2021, 2, 22), 40)  # spans the 2021-03-14 New York daylight-saving change and a month boundary
    B.build("XAUUSD", log=lambda m: None)
    res = B.verify_timeframes("XAUUSD", log=lambda m: None)
    assert set(res) >= {"M5", "H2", "H6", "H8", "H12", "D1", "W1", "MN1", "D1_NY"}
    assert all(r["identical"] for r in res.values()), res
    ny = pl.read_parquet(store / "clean" / "XAUUSD" / "D1_NY" / "all.parquet")
    hours = {t.date(): t.hour for t in ny["ts"]}
    assert hours[date(2021, 3, 8)] == 22 and hours[date(2021, 3, 15)] == 21  # 17:00 New York in UTC, winter then summer
    mn = pl.read_parquet(store / "clean" / "XAUUSD" / "MN1" / "all.parquet")
    assert [t.day for t in mn["ts"]] == [1, 1, 1] and mn["n_minutes"].sum() == pl.read_parquet(
        store / "clean" / "XAUUSD" / "D1" / "all.parquet")["n_minutes"].sum()


def test_sync_uses_only_completed_candles_and_truncation_changes_nothing():
    rng = np.random.default_rng(0)
    t0 = int(datetime(2020, 1, 6, tzinfo=timezone.utc).timestamp())
    h1 = pl.DataFrame({"ts": [datetime.fromtimestamp(t0 + 3600 * i, timezone.utc) for i in range(2000)],
                       **{f"bid_{k}": 1500 + rng.normal(0, 1, 2000) for k in ("open", "high", "low", "close")}})
    d1 = B.resample(h1.with_columns(**{f"ask_{k}": pl.col(f"bid_{k}") for k in ("open", "high", "low", "close")},
                                    bid_volume=pl.lit(1.0), ask_volume=pl.lit(1.0)), "1d")
    full = Sy.Frame(d1, "D1")
    t = t0 + rng.integers(0, 2000 * 3600, 500)
    i = full.available(t)
    assert (full.close_ts[i[i >= 0]] <= t[i >= 0]).all()  # never a candle that had not closed yet
    assert ((i + 1 >= len(full)) | (full.close_ts[np.minimum(i + 1, len(full) - 1)] > t)).all()  # and the latest one that had
    lv = Sy.previous_period_levels(full, t)
    for T in t[:50]:  # rebuild from data truncated at T: identical previous-day levels for every decision <= T
        cut = Sy.Frame(d1.filter(pl.Series(full.close_ts <= T)), "D1")
        sel = t <= T
        lc = Sy.previous_period_levels(cut, t[sel])
        assert np.allclose(lc["high"], lv["high"][sel], equal_nan=True)
    mn = Sy.bar_close("MN1", np.array([int(datetime(2024, 2, 1, tzinfo=timezone.utc).timestamp())]))
    assert datetime.fromtimestamp(int(mn[0]), timezone.utc) == datetime(2024, 3, 1, tzinfo=timezone.utc)  # leap February


def test_split_is_70_15_15_on_saturdays_frozen_and_tamper_evident(store):
    write_days(date(2021, 1, 4), 120)
    B.build("XAUUSD", log=lambda m: None)
    s = Sp.freeze_split("XAUUSD", log=lambda m: None)
    b1, b2 = datetime.fromisoformat(s["train"]["end_exclusive"]), datetime.fromisoformat(s["validation"]["end_exclusive"])
    assert b1.weekday() == 5 and b2.weekday() == 5 and b1.hour == 0 and b1 < b2
    tot = s["m1_rows_total"]
    week = 6 * 1440 / tot  # moving a cut to the next Saturday adds at most a week (6 trading days): large on 17 synthetic weeks, <0.1% on 23 years
    assert 0.70 <= s["train"]["m1_rows"] / tot <= 0.70 + week and 0.15 - week <= s["validation"]["m1_rows"] / tot <= 0.15 + week
    assert s["train"]["m1_rows"] + s["validation"]["m1_rows"] + s["test"]["m1_rows_when_frozen"] == tot
    assert Sp.freeze_split("XAUUSD", log=lambda m: None)["sha256"] == s["sha256"]  # never recomputed
    p = Sp.split_path("XAUUSD")
    edited = json.loads(p.read_text())
    edited["train"]["end_exclusive"] = edited["validation"]["end_exclusive"]
    p.write_text(json.dumps(edited))
    with pytest.raises(RuntimeError, match="edited"):
        Sp.load_split("XAUUSD")


def test_sealed_loader_refuses_the_test_period_and_logs_the_final_test(store):
    write_days(date(2021, 1, 4), 120)
    B.build("XAUUSD", log=lambda m: None)
    s = Sp.freeze_split("XAUUSD", log=lambda m: None)
    b1 = int(datetime.fromisoformat(s["train"]["end_exclusive"]).timestamp())
    b2 = int(datetime.fromisoformat(s["validation"]["end_exclusive"]).timestamp())
    for tf in ("H1", "D1", "W1"):
        tr = St.load_tf("XAUUSD", tf, "train")
        assert (Sy.bar_close(tf, Sy.epoch(tr["ts"])) <= b1).all()
        va = St.load_tf("XAUUSD", tf, "validation")
        assert va.height > tr.height and (Sy.bar_close(tf, Sy.epoch(va["ts"])) <= b2).all()
    with pytest.raises(St.SealError):
        St.load_tf("XAUUSD", "H1", "test")
    with pytest.raises(St.SealError):
        St.load_m1("XAUUSD", "test")
    log = store / "research" / "XAUUSD_seal_log.md"
    assert not log.exists()
    assert St.load_tf("XAUUSD", "H1", "test", final_test=True).height > St.load_tf("XAUUSD", "H1", "validation").height
    assert "H1 candles" in log.read_text()
    St.build_m1_store("XAUUSD", log=lambda m: None)
    m1 = St.load_m1("XAUUSD", "train")
    assert m1.ts[-1] + 60 <= b1 and m1.bid.dtype == np.int32 and m1.bid.shape[1] == 4
    clean = pl.read_parquet(sorted((store / "clean" / "XAUUSD" / "M1").glob("*.parquet"))[0])
    assert m1.bid[0, 1] * 1e-3 == pytest.approx(clean["bid_high"][0], abs=1e-6)


def test_quality_report_and_dukascopy_frames(store):
    write_days(date(2021, 3, 1), 9)
    B.build("XAUUSD", log=lambda m: None)
    B.verify_timeframes("XAUUSD", log=lambda m: None)
    md = Q.report("XAUUSD", log=lambda m: None)
    assert "| Timestamps strictly increasing | yes |" in md and "Bid and ask" in md and "| H12 |" in md
    assert (store / "reports" / "XAUUSD_raw_manifest.txt").read_text().count("\n") == 2 * 8  # 8 weekdays/Sundays x 2 sides
    payload = bi5([(0, 1800.0, 1801.0, 1799.0, 1800.5, 5.0), (3600, 1800.5, 1802.0, 1800.0, 1801.0, 0.0)])
    f = R.to_frame(payload, 1e-3, datetime(2021, 3, 1, tzinfo=timezone.utc))
    assert f["ts"][1] == datetime(2021, 3, 1, 1, tzinfo=timezone.utc) and f["high"][0] == pytest.approx(1801.0)
    ours = pl.DataFrame({"ts": [f["ts"][0]], "bid_open": [1800.0], "bid_high": [1801.0], "bid_low": [1799.0], "bid_close": [1800.5]})
    c = R.compare(ours, f, 1e-3)
    assert c["matched_timestamps"] == 1 and c["dukascopy_traded"] == 1 and c["high_match_pct"] == 100.0  # filler hour skipped

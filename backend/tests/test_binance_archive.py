"""BTCUSDT history from Binance's public archive, and the continuous (24/7) calendar in the historical store."""
import hashlib
import io
import zipfile
from datetime import datetime, timezone

import polars as pl
import pytest

from app.historical import binance_archive as ba
from app.historical import build
from app.historical.split import next_boundary

UTC = timezone.utc


def _row(open_time: int, o: float, h: float, lo: float, c: float, v: float = 2.0, tb: float = 1.0) -> list:
    # Binance kline CSV: open time, o, h, l, c, volume, close time, quote volume, trades, taker buy base, taker buy quote, ignore
    return [open_time, o, h, lo, c, v, open_time + 59_999, v * c, 10, tb, tb * c, 0]


def _zip(rows: list[list], name: str = "BTCUSDT-1m-2024-01.csv") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, "\n".join(",".join(str(x) for x in r) for r in rows) + "\n")
    return buf.getvalue()


def test_month_url_points_at_the_spot_monthly_1m_archive():
    assert ba.month_url("BTCUSDT", "2024-01") == \
        "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01.zip"


def test_parse_month_normalises_ms_and_us_open_times():
    df = ba.parse_month(_zip([_row(1704067200000, 1, 2, 0.5, 1.5), _row(1735689600000000, 1, 2, 0.5, 1.5)]))
    assert df["ts"].to_list() == [datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC)]
    assert df.columns == ["ts", "open", "high", "low", "close", "volume", "taker_buy_base"]


def test_parse_month_accepts_a_header_line():
    raw = _zip([["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "count",
                 "taker_buy_volume", "taker_buy_quote_volume", "ignore"], _row(1704067200000, 1, 2, 0.5, 1.5)])
    assert ba.parse_month(raw).height == 1


def test_checksum_mismatch_is_rejected_and_file_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(ba, "RAW_BINANCE", tmp_path)
    good = _zip([_row(1704067200000, 1, 2, 0.5, 1.5)])
    digest = hashlib.sha256(good).hexdigest()
    served = {"zip": [b"corrupted bytes", good]}  # the first download is corrupt, the retry is good

    def fetch(url: str) -> bytes:
        if url.endswith(".CHECKSUM"):
            return f"{digest}  BTCUSDT-1m-2024-01.zip\n".encode()
        return served["zip"].pop(0)

    out = ba.download("BTCUSDT", start="2024-01", end="2024-01", fetch=fetch, sleep=lambda s: None, log=lambda m: None)
    path = tmp_path / "BTCUSDT" / "BTCUSDT-1m-2024-01.zip"
    assert out["downloaded"] == 1 and out["checksum_retries"] == 1 and out["failed"] == []
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    again = ba.download("BTCUSDT", start="2024-01", end="2024-01", fetch=fetch, sleep=lambda s: None, log=lambda m: None)
    assert again["downloaded"] == 0 and again["skipped"] == 1  # resumable: a verified month is not fetched again


def test_a_month_that_never_verifies_is_reported_failed_and_not_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(ba, "RAW_BINANCE", tmp_path)

    def fetch(url: str) -> bytes:
        return b"0" * 64 + b"  x.zip" if url.endswith(".CHECKSUM") else b"never matches"

    out = ba.download("BTCUSDT", start="2024-01", end="2024-01", fetch=fetch, sleep=lambda s: None, log=lambda m: None, attempts=3)
    assert out["failed"] == ["2024-01"] and not (tmp_path / "BTCUSDT" / "BTCUSDT-1m-2024-01.zip").exists()


def test_clean_m1_uses_the_store_schema_with_the_cost_model(tmp_path, monkeypatch):
    monkeypatch.setattr(ba, "RAW_BINANCE", tmp_path / "raw")
    monkeypatch.setattr(ba, "CLEAN", tmp_path / "clean")
    d = tmp_path / "raw" / "BTCUSDT"
    d.mkdir(parents=True)
    rows = [_row(1704067200000 + k * 60_000, 100 + k, 101 + k, 99 + k, 100.5 + k, v=3.0, tb=2.0) for k in range(3)]
    rows.append(rows[0])  # a duplicate minute is dropped
    rows.append(_row(1704067200000 + 3 * 60_000, 100, 99, 101, 100))  # high below low: invalid, dropped
    (d / "BTCUSDT-1m-2024-01.zip").write_bytes(_zip(rows))
    stats = ba.write_clean_m1("BTCUSDT", half_spread=1.0, log=lambda m: None)
    df = pl.read_parquet(tmp_path / "clean" / "BTCUSDT" / "M1" / "2024.parquet")
    assert stats[2024]["clean_rows"] == 3 and stats[2024]["duplicates"] == 1 and stats[2024]["invalid_candles"] == 1
    assert df.columns == ["ts", "bid_open", "bid_high", "bid_low", "bid_close", "bid_volume", "ask_open", "ask_high", "ask_low",
                          "ask_close", "ask_volume", "spread", "taker_buy_base"]
    assert df["bid_close"].to_list() == [99.5, 100.5, 101.5] and df["ask_close"].to_list() == [101.5, 102.5, 103.5]
    assert df["bid_volume"].to_list() == [3.0] * 3 and df["ask_volume"].to_list() == [0.0] * 3
    assert df["taker_buy_base"].to_list() == [2.0] * 3 and df["spread"].to_list() == [2.0] * 3


def test_resampling_sums_taker_buy_volume_when_present():
    ts = [datetime(2024, 1, 1, 0, m, tzinfo=UTC) for m in range(10)]
    one = {f"{p}_{k}": [1.0] * 10 for p in ("bid", "ask") for k in ("open", "high", "low", "close")}
    df = pl.DataFrame({"ts": ts, **one, "bid_volume": [1.0] * 10, "ask_volume": [0.0] * 10, "taker_buy_base": [0.5] * 10})
    m5 = build.resample(df, "5m")
    assert m5["taker_buy_base"].to_list() == [2.5, 2.5]
    assert "taker_buy_base" not in build.resample(df.drop("taker_buy_base"), "5m").columns


def test_continuous_split_snaps_to_monday_and_fx_to_saturday():
    t = datetime(2024, 5, 8, 13, tzinfo=UTC)  # a Wednesday
    assert next_boundary(t, "continuous") == datetime(2024, 5, 13, tzinfo=UTC)
    assert next_boundary(t, "fx_weekly") == datetime(2024, 5, 11, tzinfo=UTC)


def test_continuous_calendar_counts_weekend_minutes_as_open():
    start, end = datetime(2024, 5, 11, 10, tzinfo=UTC), datetime(2024, 5, 11, 12, tzinfo=UTC)  # a Saturday morning
    published = pl.datetime_range(start, end, "1m", closed="left", time_zone="UTC", eager=True)
    published = published.filter((published < datetime(2024, 5, 11, 10, 30, tzinfo=UTC)) |
                                 (published >= datetime(2024, 5, 11, 11, 10, tzinfo=UTC)))  # 40 minutes missing
    gaps, expected, present = build.find_gaps("BTCUSDT", published, start, end)
    assert expected == 120 and present == 80 and gaps["material"].to_list() == [True]
    gaps_fx, expected_fx, _ = build.find_gaps("XAUUSD", published, start, end)
    assert expected_fx == 0 and gaps_fx.is_empty()  # the same hours are a scheduled closure for gold


def test_the_dukascopy_downloader_never_gets_a_binance_instrument():
    from app.historical.__main__ import dukascopy_only
    assert dukascopy_only(["XAUUSD", "BTCUSDT", "EURUSD"]) == ["XAUUSD", "EURUSD"]


def test_raw_manifest_lists_every_verified_zip_with_its_hash_and_size(tmp_path, monkeypatch):
    monkeypatch.setattr(ba, "RAW_BINANCE", tmp_path / "raw" / "binance")
    monkeypatch.setattr(ba, "REPORTS", tmp_path / "reports")
    d = tmp_path / "raw" / "binance" / "BTCUSDT"
    d.mkdir(parents=True)
    a, b = _zip([_row(1704067200000, 1, 2, 0.5, 1.5)]), _zip([_row(1706745600000, 1, 2, 0.5, 1.5)], "BTCUSDT-1m-2024-02.csv")
    (d / "BTCUSDT-1m-2024-02.zip").write_bytes(b)
    (d / "BTCUSDT-1m-2024-01.zip").write_bytes(a)
    out = ba.raw_manifest("BTCUSDT")
    text = (tmp_path / "reports" / "BTCUSDT_raw_manifest.txt").read_text()
    assert text.splitlines() == [f"{hashlib.sha256(a).hexdigest()}  {len(a)}  binance/BTCUSDT/BTCUSDT-1m-2024-01.zip",
                                 f"{hashlib.sha256(b).hexdigest()}  {len(b)}  binance/BTCUSDT/BTCUSDT-1m-2024-02.zip"]
    assert out["files"] == 2 and out["sha256"] == hashlib.sha256(text.encode()).hexdigest()


def test_btcusdt_final_period_is_sealed():
    from app.historical.split import split_path
    from app.historical.store import SealError, load_tf
    if not split_path("BTCUSDT").exists():
        pytest.skip("BTCUSDT split not frozen on this machine")
    with pytest.raises(SealError):
        load_tf("BTCUSDT", "H1", upto="test")

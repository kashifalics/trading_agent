import numpy as np
import pytest

from app.chart_vision.extraction import extract_candles, fit_axis, to_ohlc
from app.chart_vision.ocr import AxisLabel, parse_chart_title
from app.chart_vision.upload import validate_and_store
from app.chart_vision.validation import match_to_market
from app.core.exceptions import ValidationFailed
from tests.chart_fixtures import png_bytes, render_chart


def walk_ohlc(n=60, seed=2, base=2000.0):
    rng = np.random.default_rng(seed)
    out, p = [], base
    for _ in range(n):
        o, c = p, p + rng.normal(0, 4)
        out.append((o, max(o, c) + abs(rng.normal(0, 2)), min(o, c) - abs(rng.normal(0, 2)), c))
        p = c
    return out


def test_extracts_every_candle_and_recovers_prices_within_a_pixel_or_two():
    ohlc = walk_ohlc()
    img, info = render_chart(ohlc)
    ex = extract_candles(img)
    assert len(ex.candles) == 60 and ex.detected_ratio > 0.95 and ex.body_resolution == 1.0
    cal = fit_axis([AxisLabel(100, info["price_of"](100)), AxisLabel(500, info["price_of"](500))], "user")
    assert cal and cal.r2 > 0.999999
    got = to_ohlc(ex, cal, img.shape[0])
    tol = 2.5 * info["ppy"]
    for g, (o, h, lo, c) in zip(got, ohlc):
        assert abs(g["close"] - c) < tol and abs(g["open"] - o) < tol
        assert abs(g["high"] - h) < tol and abs(g["low"] - lo) < tol
        assert g["bullish"] == (c >= o)


def test_volume_bars_are_not_mistaken_for_candles():
    img, _ = render_chart(walk_ohlc(), with_volume=True)
    ex = extract_candles(img)
    assert len(ex.candles) == 60
    assert any("volume" in w for w in ex.warnings)


def test_uncalibrated_output_is_pixel_units_not_prices():
    img, _ = render_chart(walk_ohlc())
    ex = extract_candles(img)
    out = to_ohlc(ex, None, img.shape[0])
    assert all(0 < c["close"] < img.shape[0] for c in out)  # pixel units, clearly not ~2000-price scale


def test_axis_fit_rejects_nonsense():
    assert fit_axis([AxisLabel(100, 10), AxisLabel(300, 20)], "ocr") is None  # price rising downwards
    assert fit_axis([AxisLabel(100, 10)], "ocr") is None
    pts = [AxisLabel(100, 2100), AxisLabel(200, 2050), AxisLabel(300, 1900), AxisLabel(400, 1950)]
    assert fit_axis(pts, "ocr", min_points=3) is None  # inconsistent labels (R^2 too low)
    assert fit_axis([AxisLabel(100, 2100), AxisLabel(200, 2050), AxisLabel(300, 2000)], "ocr", min_points=3)


def test_few_candles_reported():
    img, _ = render_chart(walk_ohlc(3))
    ex = extract_candles(img)
    assert "fewer than 5" in " ".join(ex.warnings)


def test_title_parsing_exact_aliases_only():
    assert parse_chart_title("XAUUSD, 1H  O2350.1") [:2] == ("XAUUSD", "1H")
    assert parse_chart_title("Dow Jones US30  15m")[:2] == ("US30", "15m")
    sym, tf, notes = parse_chart_title("BTCUSD 4h")
    assert sym is None and tf == "4H" and notes
    assert parse_chart_title("hello world")[:2] == (None, None)
    sym, tf, notes = parse_chart_title("BICUSDT 1H Binance")  # one OCR slip is tolerated, loudly
    assert (sym, tf) == ("BTCUSDT", "1H") and "verify" in notes[0]
    assert parse_chart_title("XAUUSZ 1H")[0] == "XAUUSD"
    assert parse_chart_title("ETHUSDT 1H")[0] is None  # two edits away: never guessed


def test_market_match_is_scale_invariant_and_rejects_noise():
    rng = np.random.default_rng(5)
    close = 100 + np.cumsum(rng.normal(0, 1, 400))
    rng_ = np.abs(rng.normal(1, 0.3, 400))
    window = slice(200, 260)
    ex_close, ex_range = close[window] * 7.5 - 300, rng_[window] * 7.5  # different "pixel" scale
    m = match_to_market(ex_close, ex_range, close, rng_)
    assert m and m["start"] == 200 and m["end"] == 259
    noise = 100 + np.cumsum(np.random.default_rng(99).normal(0, 1, 60))
    assert match_to_market(noise, np.abs(np.random.default_rng(98).normal(1, .3, 60)), close, rng_) is None


def test_upload_validation(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    img, _ = render_chart(walk_ohlc(20))
    stored = validate_and_store(png_bytes(img), "../../evil name.png", user_id=7)
    assert stored.filename == "evil_name.png" and stored.path.startswith(str(tmp_path)) and stored.path.endswith(".png")
    for bad in (b"", b"GIF89a....", b"<script>alert(1)</script>", b"\x89PNG\r\n\x1a\nnot really a png"):
        with pytest.raises(ValidationFailed):
            validate_and_store(bad, "x.png", 7)
    tiny, _ = render_chart(walk_ohlc(5), width=100, height=60, top=5, bottom=5)
    with pytest.raises(ValidationFailed):
        validate_and_store(png_bytes(tiny), "tiny.png", 7)
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1000")
    get_settings.cache_clear()
    with pytest.raises(ValidationFailed):
        validate_and_store(png_bytes(img), "big.png", 7)
    get_settings.cache_clear()

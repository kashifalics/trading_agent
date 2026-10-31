"""Keeps the five notions of 'how sure are we' SEPARATE. None of them is blended into one number."""
from datetime import datetime, timezone

from app.market_data.timeframes import approx_seconds, get_timeframe

PASSED = "passed_minimum_checks"


def data_quality(*, n_bars: int, last_bar_ts: int | None, timeframe: str, gap_count_recent: int,
                 provider_status: str, now: datetime | None = None, price_calibrated: bool = True,
                 source: str = "market_data") -> dict:
    now = now or datetime.now(timezone.utc)
    issues, score = [], 1.0
    if n_bars < 300:
        issues.append(f"only {n_bars} complete bars (< 300)")
        score -= 0.5
    elif n_bars < 1000:
        issues.append(f"{n_bars} bars: limited history for analogue/ML evidence")
        score -= 0.1
    if last_bar_ts is not None:
        step = approx_seconds(get_timeframe(timeframe))
        age = now.timestamp() - last_bar_ts - step
        if age > 3 * step and get_timeframe(timeframe).kind in ("intraday",):
            issues.append(f"latest complete candle is {age / step:.0f} bars old (data may be stale or market closed)")
            score -= 0.3
    if gap_count_recent:
        issues.append(f"{gap_count_recent} gap(s) in stored history")
        score -= min(0.3, 0.05 * gap_count_recent)
    if provider_status != "active":
        issues.append(f"provider mapping status is '{provider_status}' (not independently verified)")
        score -= 0.2
    if not price_calibrated:
        issues.append("prices are not calibrated to a real scale (screenshot extraction)")
        score -= 0.6
    if source == "screenshot":
        issues.append("derived from a screenshot, not from provider candles")
        score -= 0.2
    return {"score": max(0.0, round(score, 3)), "issues": issues}


def confidence_panel(*, ml: dict | None, analogues: dict | None, confluence: float | None,
                     confluence_components: list[dict], quality: dict, warnings: list[str]) -> dict:
    model_prob = None
    research = None
    if ml:
        out = {"p_long_tp_first": ml["p_long_tp_first"], "p_short_tp_first": ml["p_short_tp_first"],
               "p_neither": ml["p_neither"], "model_version_id": ml.get("model_version_id")}
        if ml.get("is_calibrated") and ml.get("validation_status") == PASSED:
            model_prob = out
        else:
            research = {**out, "validation_status": ml.get("validation_status"),
                        "note": "Research-only model: output shown for transparency, excluded from the decision."}
    hist = None
    if analogues and analogues.get("stats"):
        s = analogues["stats"]
        hist = {"long_tp_before_sl": s["long_tp_before_sl"], "short_tp_before_sl": s["short_tp_before_sl"],
                "base_rate_long": s["base_rate_long"], "base_rate_short": s["base_rate_short"],
                "n_obs": analogues["n_obs"], "sufficient": analogues["sufficient"],
                "label": "historical frequency of similar situations, not a probability forecast"}
    return {
        "model_probability": model_prob, "research_only_model_output": research,
        "historical_frequency": hist,
        "analytical_confluence": {"score": confluence, "scale": "[-1, +1], +1 = fully bullish agreement",
                                  "components": confluence_components},
        "data_quality": quality,
        "uncertainty": warnings,
    }

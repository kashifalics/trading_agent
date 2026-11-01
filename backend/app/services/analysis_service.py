import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.jsonutil import to_jsonable
from app.database.base import utcnow
from app.database.models import (
    Analysis,
    HistoricalAnalogue,
    Instrument,
    ModelVersion,
    Prediction,
    PredictionEvidence,
    PriceActionEvent,
)
from app.feature_engineering.labels import LabelConfig
from app.market_data.ingestion.service import resolve_mapping
from app.ml_engine.inference import load_bundle
from app.ml_engine.model_registry import get_active_model
from app.multi_timeframe.analysis import MTFConfig
from app.prediction.confidence import data_quality
from app.services.data_service import ensure_data, load_bars, recent_gap_count
from app.services.pattern_scan import study_caveat
from app.services.pipeline import (
    PipelineOutput,
    overlay_events,
    run_pipeline,
    swing_points,
)

log = logging.getLogger(__name__)


def _dec(x, places: int) -> Decimal | None:
    return None if x is None else Decimal(str(round(float(x), places + 2)))


def create_analysis(session: Session, user_id: int, params: dict) -> Analysis:
    inst, prov, _ = resolve_mapping(session, params["symbol"], params.get("provider"))  # fail fast if unsupported
    a = Analysis(user_id=user_id, instrument_id=inst.id, provider_id=prov.id, timeframe=params["timeframe"],
                 source=params.get("source", "market_data"), status="queued", params=to_jsonable(params))
    session.add(a)
    session.commit()
    return a


def run_analysis_job(analysis_id: int) -> None:
    from app.database.session import session_scope

    with session_scope() as session:
        a = session.get(Analysis, analysis_id)
        if a is None:
            return
        a.status, a.started_at = "running", utcnow()
        session.commit()
        try:
            execute_analysis(session, a)
            a.status = "completed"
        except AppError as exc:
            session.rollback()
            a = session.get(Analysis, analysis_id)
            a.status, a.error = "failed", exc.message
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("analysis %s crashed", analysis_id)
            session.rollback()
            a = session.get(Analysis, analysis_id)
            a.status, a.error = "failed", f"internal error ({exc.__class__.__name__})"
        a.completed_at = utcnow()
        session.commit()


def execute_analysis(session: Session, a: Analysis, bars_override=None, price_calibrated: bool = True,
                     source: str = "market_data", extra_warnings: list[str] | None = None,
                     provider_label: str | None = None) -> PipelineOutput:
    """bars_override: pre-built bars (screenshot path). No provider mapping/sync is needed then, so
    instruments without a configured feed (US30, USOIL) can still be analysed from a screenshot."""
    p = a.params or {}
    inst = session.get(Instrument, a.instrument_id)
    if bars_override is None:
        inst, prov, pi = resolve_mapping(session, inst.canonical_symbol, p.get("provider"))
        prov_code, pi_status, gaps = prov.code, pi.status, recent_gap_count(session, inst, prov, a.timeframe)
    else:
        prov_code, pi_status, gaps = provider_label or "screenshot", "active", 0
    tf = a.timeframe
    warnings: list[str] = list(extra_warnings or [])
    lookback = int(p.get("lookback_bars", 1500))
    mtf_in = p.get("mtf") or {}
    mtf_cfg = MTFConfig(mtf_in.get("higher"), mtf_in.get("intermediate"), mtf_in.get("entry"))

    if bars_override is None:
        warnings += ensure_data(session, inst, prov, pi, tf, lookback, p.get("auto_sync", True))
        bars = load_bars(session, inst, prov, tf, lookback)
    else:
        bars = bars_override
    if len(bars) == 0:
        raise AppError(f"No stored candles for {inst.canonical_symbol} {tf} from {prov_code}. Sync data first.")

    mtf_bars = {}
    for _, mtf_tf in mtf_cfg.roles():
        if mtf_tf == tf or bars_override is not None:
            continue
        warnings += ensure_data(session, inst, prov, pi, mtf_tf, 600, p.get("auto_sync", True))
        mtf_bars[mtf_tf] = load_bars(session, inst, prov, mtf_tf, 600)

    label_cfg = LabelConfig(int(p.get("horizon_bars", 24)), float(p.get("tp_atr", 2.0)), float(p.get("sl_atr", 1.0)))
    ml_bundle, ml_meta = None, None
    if p.get("use_ml", True) and bars_override is None:
        mv = get_active_model(session, inst.id, prov.id, tf)
        if mv:
            ml_bundle = load_bundle(mv)
            if ml_bundle:
                ml_meta = {"model_version_id": mv.id, "algorithm": mv.algorithm, "validation_status": mv.validation_status,
                           "is_calibrated": mv.is_calibrated, "version": mv.version}
                label_cfg = LabelConfig(**ml_bundle["label_cfg"])

    quality = data_quality(n_bars=len(bars), last_bar_ts=int(bars.t[-1]), timeframe=tf,
                           gap_count_recent=gaps, provider_status=pi_status,
                           price_calibrated=price_calibrated, source=source)
    out = run_pipeline(symbol=inst.canonical_symbol, timeframe=tf, bars=bars, quality=quality, label_cfg=label_cfg,
                       min_rr=float(p.get("min_rr", 1.5)), mtf_cfg=mtf_cfg, mtf_bars=mtf_bars, ml_bundle=ml_bundle,
                       ml_meta=ml_meta, price_calibrated=price_calibrated)
    persist_result(session, a, inst, prov_code, out, bars, warnings, ml_meta)
    return out


def persist_result(session: Session, a: Analysis, inst: Instrument, provider_code: str, out: PipelineOutput, bars,
                   warnings: list[str], ml_meta: dict | None) -> Prediction:
    d = out.decision
    places = inst.price_precision
    as_of = datetime.fromtimestamp(int(bars.t[-1]) + bars.step, tz=timezone.utc)
    dec = d.to_dict()
    dec["warnings"] = list(dict.fromkeys(dec["warnings"] + warnings))
    if d.decision != "WAIT":
        caveat = study_caveat(inst.canonical_symbol)
        if caveat:
            dec["warnings"].append(caveat)
    events = overlay_events(out.pa, out.n_bars)
    a.as_of_ts = as_of
    a.result = to_jsonable({
        "decision": dec, "events": events, "swings": swing_points(out.pa, out.n_bars, bars),
        "analogues": out.analogues.to_dict() if out.analogues else None, "mtf": out.mtf,
        "atr": out.pa.atr[-1] if out.n_bars else None, "last_close": bars.c[-1], "bars_used": out.n_bars,
        "model": ml_meta,
    })
    session.execute(delete(PriceActionEvent).where(PriceActionEvent.analysis_id == a.id))
    session.execute(delete(HistoricalAnalogue).where(HistoricalAnalogue.analysis_id == a.id))
    for e in events[-200:]:
        session.add(PriceActionEvent(
            analysis_id=a.id, instrument_id=inst.id, timeframe=a.timeframe, kind=e["kind"], direction=e["direction"],
            ts=datetime.fromtimestamp(e["ts"], tz=timezone.utc), level_low=_dec(e["low"], places),
            level_high=_dec(e["high"], places) if e["high"] is not None else _dec(e["price"], places),
            status=e["status"], evidence={"text": e["evidence"]}))
    if out.analogues:
        for rank, nb in enumerate(out.analogues.neighbors[:25], 1):
            session.add(HistoricalAnalogue(
                analysis_id=a.id, rank=rank, matched_ts=datetime.fromtimestamp(nb["ts"], tz=timezone.utc),
                similarity=nb["similarity"], horizon_bars=out.analogues.stats["horizon_bars"],
                forward_return=nb["forward_return_atr"], mfe_atr=nb["mfe_atr"], mae_atr=nb["mae_atr"],
                long_tp_before_sl=nb["long_tp_before_sl"], short_tp_before_sl=nb["short_tp_before_sl"],
                meta={"idx": nb["idx"], "distance": nb["distance"]}))
    plan = d.plan
    panel = d.panel
    pred = Prediction(
        analysis_id=a.id, user_id=a.user_id, instrument_id=inst.id, provider_code=provider_code, timeframe=a.timeframe,
        decision=d.decision, entry_low=_dec(plan.entry_low, places) if plan else None,
        entry_high=_dec(plan.entry_high, places) if plan else None, stop_loss=_dec(plan.stop_loss, places) if plan else None,
        take_profit=[round(t, places) for t in plan.targets] if plan else None,
        risk_reward=plan.risk_reward if plan else None, invalidation_level=_dec(plan.invalidation, places) if plan else None,
        model_version_id=(ml_meta or {}).get("model_version_id"),
        probabilities=to_jsonable(panel["model_probability"]), historical_frequency=to_jsonable(panel["historical_frequency"]),
        confluence_score=d.confluence, data_quality_score=panel["data_quality"]["score"],
        warnings=dec["warnings"], explanation=d.explanation, as_of_ts=as_of,
        outcome="open" if plan else "not_applicable", outcome_meta={"wait_reasons": d.wait_reasons} if not plan else None)
    session.add(pred)
    session.flush()
    for e in d.evidence:
        session.add(PredictionEvidence(
            prediction_id=pred.id, category=e["category"], name=e["name"], direction=e["direction"], weight=e["weight"],
            score=e["score"], detail=e["detail"], ts=datetime.fromisoformat(e["ts"]) if e["ts"] else None,
            price=_dec(e["price"], places)))
    session.commit()
    return pred


def prediction_for_analysis(session: Session, analysis_id: int) -> Prediction | None:
    return session.scalar(select(Prediction).where(Prediction.analysis_id == analysis_id))


__all__ = ["create_analysis", "run_analysis_job", "execute_analysis", "persist_result", "ModelVersion"]

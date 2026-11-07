"""Per-timeframe loading, derivation, freshness, signature and descriptive result (independent of any trade setup)."""
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models import DataProvider, Instrument, ProviderInstrument
from app.market_data.aggregation.aggregate import aggregate_candles
from app.market_data.bars import Bars
from app.market_data.coverage.gaps import find_gaps, staleness
from app.market_data.ingestion.service import anchor_for, load_candles
from app.market_data.timeframes import approx_seconds, get_timeframe
from app.multi_timeframe.alignment import TFView, alignment, build_view, htf_as_of
from app.opportunities.config import (
    BIAS_TFS,
    CONFIG_VERSION,
    DERIVE_FROM,
    MIN_STRUCTURE_BARS,
    SCAN_LOOKBACK_BARS,
)
from app.opportunities.setup import Bias, Concepts, compute_concepts
from app.prediction.confidence import data_quality
from app.price_action.engine import PriceActionResult, analyze_price_action
from app.services.data_service import load_bars, tf_step, trading_hours_only

NATIVE_FIELD = {"binance": "binance", "twelve_data": "twelve_data"}


def provider_configured(code: str) -> tuple[bool, str | None]:
    s = get_settings()
    if code == "binance":
        return True, None
    if code == "twelve_data":
        return (True, None) if s.twelve_data_api_key else (False, "TWELVE_DATA_API_KEY is not configured")
    if code == "biquote":
        return True, None  # public API: no key to configure
    if code == "oanda":
        return (True, None) if s.oanda_api_token else (False, "OANDA_API_TOKEN is not configured (no verified data source for this instrument)")
    return False, f"no adapter for provider '{code}'"


def natively_supported(provider: str, tf: str) -> bool:
    attr = NATIVE_FIELD.get(provider)
    return True if attr is None else getattr(get_timeframe(tf), attr) is not None


@dataclass
class TF:
    """Everything known about one timeframe of one instrument. Heavy objects (PA, concepts) are computed lazily and once."""
    tf: str
    status: str  # completed | insufficient_data | unsupported | failed
    bars: Bars | None = None
    n_bars: int = 0
    signature: str | None = None
    derived_from: str | None = None
    stale_bars: float | None = None
    gap_count: int = 0
    quality: dict = field(default_factory=lambda: {"score": 0.0, "issues": []})
    error: str | None = None
    reason: str | None = None
    _pa: PriceActionResult | None = None
    _cx: Concepts | None = None
    _feats: dict | None = None
    actx: dict = field(default_factory=dict)  # per-style analogue contexts (features + labels), built once per scan

    @property
    def pa(self) -> PriceActionResult:
        if self._pa is None:
            self._pa = analyze_price_action(self.bars)
        return self._pa

    @property
    def cx(self) -> Concepts:
        if self._cx is None:
            self._cx = compute_concepts(self.bars, self.pa)
        return self._cx

    @property
    def ok(self) -> bool:
        return self.status == "completed"

    def first_ts(self) -> datetime | None:
        return datetime.fromtimestamp(int(self.bars.t[0]), tz=timezone.utc) if self.bars is not None and len(self.bars) else None

    def last_ts(self) -> datetime | None:
        return datetime.fromtimestamp(int(self.bars.t[-1]), tz=timezone.utc) if self.bars is not None and len(self.bars) else None


def _signature(inst: Instrument, prov: DataProvider, t: TF) -> str:
    b = t.bars
    raw = (f"{CONFIG_VERSION}|{inst.id}|{prov.id}|{t.tf}|{t.n_bars}|{int(b.t[0])}|{int(b.t[-1])}|{b.c[-1]:.10g}|{b.c[0]:.10g}|"
           f"{t.derived_from}|{t.gap_count}")
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _derive(session: Session, inst: Instrument, prov: DataProvider, tf: str,
            lookback: int = SCAN_LOOKBACK_BARS) -> tuple[Bars | None, str | None]:
    base = DERIVE_FROM.get(tf)
    if not base:
        return None, None
    ratio = int(np.ceil(approx_seconds(get_timeframe(tf)) / approx_seconds(get_timeframe(base))))
    candles = load_candles(session, inst.id, prov.id, base, limit=min(lookback * ratio, 60_000), complete_only=True)
    candles = trading_hours_only(candles, inst.calendar)
    if not candles:
        return None, base
    agg = aggregate_candles(candles, base, tf, anchor_for(inst), inst.calendar)
    return _tail(Bars.from_candles(agg, tf_step(tf)), lookback), base


def _tail(b: Bars, n: int) -> Bars:
    return b.slice(max(0, len(b) - n), len(b))


def window_gaps(bars: Bars, tf: str, inst: Instrument) -> tuple[int, int]:
    """(significant, minor) gaps inside the ANALYSED window only. Minor = 1-2 missing intraday candles, which are almost always
    unmodelled maintenance breaks or holidays; significant = longer holes (or any missing candle on 1D and above)."""
    ts = [datetime.fromtimestamp(int(t), tz=timezone.utc) for t in bars.t]
    gs = find_gaps(ts, tf, inst.calendar, anchor_for(inst))
    floor = 3 if get_timeframe(tf).is_intraday else 1
    sig = sum(1 for g in gs if g["missing"] >= floor)
    return sig, len(gs) - sig


def prepare_tf(session: Session, inst: Instrument, prov: DataProvider, pi: ProviderInstrument, tf: str,
               now: datetime | None = None, lookback: int = SCAN_LOOKBACK_BARS) -> TF:
    """Load (or, only when the native series is too short, derive) completed candles for one timeframe. Never fabricates bars."""
    now = now or datetime.now(timezone.utc)
    try:
        bars = load_bars(session, inst, prov, tf, lookback)
        derived = None
        if len(bars) < MIN_STRUCTURE_BARS:
            d_bars, base = _derive(session, inst, prov, tf, lookback)
            if d_bars is not None and len(d_bars) > len(bars):
                bars, derived = d_bars, base
        n = len(bars)
        if n == 0:
            native = natively_supported(prov.code, tf)
            if not native and tf not in DERIVE_FROM:
                return TF(tf, "unsupported", reason=f"{prov.code} does not provide {tf} candles and none can be derived")
            return TF(tf, "insufficient_data", reason="no stored candles for this timeframe"
                      + (f" (derivation from {DERIVE_FROM[tf]} also found none)" if tf in DERIVE_FROM else ""))
        if n < MIN_STRUCTURE_BARS:
            return TF(tf, "insufficient_data", n_bars=n, bars=bars, derived_from=derived,
                      reason=f"only {n} complete candles (need >= {MIN_STRUCTURE_BARS} for structure analysis)")
        gaps, minor = window_gaps(bars, tf, inst)
        last = datetime.fromtimestamp(int(bars.t[-1]), tz=timezone.utc)
        stale = staleness(last, tf, now, inst.calendar, anchor_for(inst))
        q = data_quality(n_bars=n, last_bar_ts=int(bars.t[-1]), timeframe=tf, gap_count_recent=gaps, provider_status=pi.status, now=now)
        q["stale_bars"], q["gap_count"] = stale, gaps
        if minor:
            q["issues"].append(f"{minor} short gap(s) of 1-2 candles (typically daily maintenance breaks / holidays) in the analysed window: not penalised")
        t = TF(tf, "completed", bars, n, None, derived, stale, gaps, q)
        if derived:
            q["issues"].append(f"built from stored {derived} candles (complete buckets only)")
        t.signature = _signature(inst, prov, t)
        return t
    except Exception as exc:  # noqa: BLE001 - one bad timeframe must not fail the whole scan
        return TF(tf, "failed", error=f"{exc.__class__.__name__}: {exc}"[:300])


# ----------------------------------------------------------------------------- descriptive result for one timeframe
def _slim(e) -> dict:
    return {"kind": e.kind, "direction": e.direction, "ts": e.ts, "price": e.price, "low": e.low, "high": e.high, "status": e.status,
            "evidence": e.evidence}


def view_of(t: TF, role: str) -> TFView:
    return build_view(t.bars, t.tf, role, t.pa)[0]


def tf_features(t: TF) -> dict:
    """Last-bar momentum/volatility numbers used by the evidence score (point-in-time)."""
    if t._feats is None:
        from app.feature_engineering.features import FEATURE_NAMES, compute_features

        _, X = compute_features(t.bars, t.pa)
        row = dict(zip(FEATURE_NAMES, X[-1]))
        atr_pct = X[:, FEATURE_NAMES.index("atr_pct")]
        ok = atr_pct[np.isfinite(atr_pct)]
        rank = float((ok < atr_pct[-1]).mean()) if len(ok) > 30 and np.isfinite(atr_pct[-1]) else None
        t._feats = {"ret_10": float(row["ret_10"]), "slope_20": float(row["slope_20"]), "rsi_14": float(row["rsi_14"]),
                    "vol_ratio": float(row["vol_ratio"]), "atr_pct_rank": rank, "atr_pct": float(row["atr_pct"])}
        t._X = X  # type: ignore[attr-defined]
    return t._feats


def tf_result(t: TF) -> dict:
    """Descriptive, trade-agnostic analysis of one timeframe (what the market is doing here)."""
    b, pa, cx = t.bars, t.pa, t.cx
    n, last = len(b), len(b) - 1
    px = float(b.c[last])
    pd_ = pa.premium_discount
    brk = pa.breaks[-1] if pa.breaks else None
    live = [z for z in pa.fvgs + pa.order_blocks + pa.breakers + pa.zones
            if z.status not in ("filled", "invalidated", "broken") and z.low is not None and last - z.idx <= 300]
    live.sort(key=lambda z: min(abs(px - z.low), abs(px - z.high)))
    cands = [e for e in pa.candles if last - e.idx < 5 and e.direction != "neutral"]
    f = tf_features(t)
    a = float(pa.atr[last]) if np.isfinite(pa.atr[last]) else None
    notable = [e for e in pa.breaks + pa.sweeps if last - e.idx <= 60][-8:]
    swings = [{"kind": s.kind, "label": s.label, "price": s.price, "ts": int(b.t[s.idx])} for s in pa.swings
              if s.confirm_idx <= last][-8:]
    return {
        "timeframe": t.tf, "n_bars": n, "first_ts": int(b.t[0]), "last_ts": int(b.t[-1]), "last_close": px, "atr": a,
        "stale_bars": t.stale_bars, "derived_from": t.derived_from, "gap_count": t.gap_count, "quality": t.quality,
        "trend": int(pa.trend[last]), "bias": int(pa.bias), "last_break": f"{brk.kind}:{brk.direction}" if brk else None,
        "last_break_bars_ago": (last - brk.idx) if brk else None,
        "zone": pd_.status if pd_ else None, "range_position": pd_.meta["position"] if pd_ else None,
        "momentum": {k: (None if v is None or not np.isfinite(v) else round(float(v), 4)) for k, v in f.items()},
        "swings": swings, "notable_events": [_slim(e) for e in notable], "recent_candles": [_slim(e) for e in cands],
        "live_zones": [{**_slim(z), "dist_atr": (min(abs(px - z.low), abs(px - z.high)) / a) if a else None} for z in live[:8]],
        "levels": [_slim(e) for e in cx.levels[:6]], "trendlines": [_slim(e) | {"meta": e.meta} for e in cx.trendlines],
        "breakouts": [_slim(e) for e in cx.breakouts[-4:]],
        "volume": {"available": bool(np.isfinite(b.v).any())},
        "summary": (f"{'bullish' if pa.trend[last] > 0 else 'bearish' if pa.trend[last] < 0 else 'undetermined'} structure"
                    + (f", last {brk.kind} {brk.direction} {last - brk.idx} bars ago" if brk else "")
                    + (f", price in {pd_.status} ({pd_.meta['position']:.0%})" if pd_ else "")),
    }


# ----------------------------------------------------------------------------- higher-timeframe bias
def build_bias(tfs: dict[str, TF], setup_tf: str) -> Bias:
    """Weighted structure direction of the available higher timeframes, as known when the setup bar closed."""
    base = tfs[setup_tf]
    end = int(base.bars.t[-1]) + base.bars.step
    views: list[TFView] = []
    for role, htf in zip(("higher", "intermediate"), reversed(BIAS_TFS.get(setup_tf, ()))):
        h = tfs.get(htf)
        if not h or not h.ok:
            continue
        cut = htf_as_of(h.bars, end)
        views.append(build_view(cut, htf, role, h.pa if len(cut) == len(h.bars) else None)[0])
    al = alignment(views) if views else {"score": 0.0, "conflict": False, "direction": 0, "views": []}
    return Bias(int(al["direction"]), float(al["score"]), bool(al["conflict"]), al.get("views", []))

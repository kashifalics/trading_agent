"""Central risk management (DESIGN section 10). Limits are configuration, not promises of safety. Position size never grows after
losses (no martingale, grid or averaging down): it is always risk % x current equity / stop distance."""
from dataclasses import asdict, dataclass

from app.strategy_engine.config import CONTRACT_SIZE, LEGS, TARGETS


@dataclass(frozen=True)
class RiskLimits:
    risk_per_trade_pct: float = 0.5
    max_concurrent: int = 5
    max_open_risk_pct: float = 2.0
    daily_loss_limit_pct: float = 2.0
    max_drawdown_pct: float = 10.0
    min_rr: float = TARGETS["tp1_min_r"]
    max_currency_exposure_pct: float = 1.5


def position_size(symbol: str, equity: float, risk_pct: float, entry: float, stop: float) -> dict:
    """Lots (and units) so that a stop-out loses risk_pct of equity. Contract sizes: CONTRACT_SIZE (1 lot)."""
    dist = abs(entry - stop)
    contract = CONTRACT_SIZE.get(symbol, 1.0)
    amount = equity * risk_pct / 100.0
    if dist <= 0 or equity <= 0:
        return {"risk_amount": amount, "units": 0.0, "lots": 0.0, "contract_size": contract}
    units = amount / dist
    return {"risk_amount": round(amount, 2), "units": units, "lots": units / contract, "contract_size": contract}


def exposure(open_trades: list[dict]) -> dict[str, float]:
    """Net open risk per currency leg in % of equity: a BUY of EURUSD adds +risk to EUR and -risk to USD."""
    out: dict[str, float] = {}
    for t in open_trades:
        base, quote = LEGS.get(t["symbol"], (t["symbol"], "USD"))
        sgn = 1 if t["direction"] == "BUY" else -1
        out[base] = out.get(base, 0.0) + sgn * t["risk_pct"]
        out[quote] = out.get(quote, 0.0) - sgn * t["risk_pct"]
    return out


def check(signal: dict, *, symbol: str, equity: float, peak_equity: float, today_pnl_pct: float, open_trades: list[dict],
          regime_label: str, session: dict, limits: RiskLimits = RiskLimits()) -> dict:
    """Eligibility of a new signal against the account state. Returns {eligible, blocks, warnings, size, exposure_after}."""
    blocks, warns = [], []
    plan = signal.get("plan") or {}
    if not plan:
        return {"eligible": False, "blocks": ["no trade plan"], "warnings": [], "size": None, "limits": asdict(limits)}
    if plan.get("risk_reward", 0) < limits.min_rr:
        blocks.append(f"TP1 reward:risk {plan.get('risk_reward', 0):.2f} below {limits.min_rr:g}")
    if regime_label == "HIGH_VOLATILITY":
        blocks.append("volatility filter: abnormal volatility")
    if not session.get("entry_allowed", True):
        blocks.append(f"session filter: {session.get('block_reason')}")
    if len(open_trades) >= limits.max_concurrent:
        blocks.append(f"{len(open_trades)} trades open (maximum {limits.max_concurrent})")
    open_risk = sum(t["risk_pct"] for t in open_trades)
    if open_risk + limits.risk_per_trade_pct > limits.max_open_risk_pct + 1e-9:
        blocks.append(f"open risk would reach {open_risk + limits.risk_per_trade_pct:.2f}% (maximum {limits.max_open_risk_pct:g}%)")
    if today_pnl_pct <= -limits.daily_loss_limit_pct:
        blocks.append(f"daily loss limit reached ({today_pnl_pct:.2f}%)")
    dd = (peak_equity - equity) / peak_equity * 100 if peak_equity > 0 else 0.0
    if dd >= limits.max_drawdown_pct:
        blocks.append(f"drawdown {dd:.1f}% from the equity peak (halt at {limits.max_drawdown_pct:g}%)")
    after = exposure(open_trades + [{"symbol": symbol, "direction": signal.get("direction") or "BUY", "risk_pct": limits.risk_per_trade_pct}])
    over = {k: v for k, v in after.items() if abs(v) > limits.max_currency_exposure_pct + 1e-9}
    if over:
        blocks.append("correlated exposure: " + ", ".join(f"{k} {v:+.2f}%" for k, v in over.items())
                      + f" (maximum {limits.max_currency_exposure_pct:g}% per currency)")
    size = position_size(symbol, equity, limits.risk_per_trade_pct, plan["entry"], plan["stop_loss"])
    return {"eligible": not blocks, "blocks": blocks, "warnings": warns, "size": size, "exposure_after": after,
            "drawdown_pct": dd, "limits": asdict(limits)}

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import numpy as np

from app.backtesting.execution import Position, check_exit
from app.backtesting.metrics import backtest_metrics
from app.backtesting.strategies import Signal, Strategy
from app.market_data.bars import Bars


@dataclass
class BacktestConfig:
    initial_equity: float = 10_000.0
    risk_pct: float = 1.0  # % of current equity risked per trade
    spread: float = 0.0  # full bid/ask spread in price units
    slippage: float = 0.0  # price units, paid on stop/market fills
    spread_pct: float = 0.0  # full spread as % of price (added to `spread`); right for long, trending histories
    slippage_pct: float = 0.0  # slippage as % of price per market/stop fill (added to `slippage`)
    commission_pct: float = 0.0  # % of notional per side
    contract_size: float = 1.0
    max_bars_in_trade: int = 200
    eval_every: int = 1  # evaluate the strategy every N bars while flat
    allowed_hours_utc: list[int] | None = None  # session filter on the SIGNAL bar
    max_leverage: float = 20.0


@dataclass
class BacktestResult:
    config: dict
    trades: list[dict]
    equity_curve: list[list]  # [ts_iso, equity]
    metrics: dict
    skipped_signals: int = 0
    meta: dict = field(default_factory=dict)


def _iso(t: int) -> str:
    return datetime.fromtimestamp(int(t), tz=timezone.utc).isoformat()


def run_backtest(bars: Bars, strategy: Strategy, cfg: BacktestConfig | None = None) -> BacktestResult:
    cfg = cfg or BacktestConfig()
    n = len(bars)
    equity = cfg.initial_equity
    eq = np.full(n, cfg.initial_equity)
    trades: list[dict] = []
    pos: Position | None = None
    skipped = 0
    entry_slip_cost = 0.0
    pending: tuple[int, Signal] | None = None

    for i in range(n):
        # 1) execute a signal generated at the close of bar i-1 at this bar's open
        if pending is not None and pos is None:
            sig_idx, sig = pending
            pending = None
            d = 1 if sig.direction == "BUY" else -1
            half = cfg.spread / 2 + cfg.spread_pct / 100 * bars.o[i] / 2  # priced at the fill bar
            slip = cfg.slippage + cfg.slippage_pct / 100 * bars.o[i]
            entry = bars.o[i] + d * (half + slip)
            risk_per_unit = abs(entry - sig.stop_loss) * cfg.contract_size
            valid = (sig.stop_loss < entry) if d == 1 else (sig.stop_loss > entry)
            if sig.take_profit is not None:
                valid = valid and ((sig.take_profit > entry) if d == 1 else (sig.take_profit < entry))
            if valid and risk_per_unit > 0:
                units = equity * cfg.risk_pct / 100 / risk_per_unit
                units = min(units, equity * cfg.max_leverage / (entry * cfg.contract_size))
                comm = units * entry * cfg.contract_size * cfg.commission_pct / 100
                equity -= comm
                pos = Position(d, i, sig_idx, entry, sig.stop_loss, sig.take_profit, units, comm)
                entry_slip_cost = (half + slip) * units * cfg.contract_size  # spread + slippage paid on entry
            else:
                skipped += 1

        # 2) manage open position on this bar
        if pos is not None:
            half = cfg.spread / 2 + cfg.spread_pct / 100 * bars.o[i] / 2
            slip = cfg.slippage + cfg.slippage_pct / 100 * bars.o[i]
            ex = check_exit(pos, bars.o[i], bars.h[i], bars.l[i], half, slip)
            held = i - pos.entry_idx + 1
            if ex is None and (held >= cfg.max_bars_in_trade or i == n - 1):
                # forced exit at the close: time stop, or position still open when the data ends
                ex = ("time" if held >= cfg.max_bars_in_trade else "end_of_data",
                      bars.c[i] - pos.direction * (half + slip))
            if ex is not None:
                reason, px = ex
                gross = (px - pos.entry_price) * pos.direction * pos.units * cfg.contract_size
                exit_comm = pos.units * px * cfg.contract_size * cfg.commission_pct / 100
                risk_cash = abs(pos.entry_price - pos.stop) * pos.units * cfg.contract_size
                pnl = gross - exit_comm - pos.entry_costs
                equity += gross - exit_comm
                trades.append({
                    "direction": "BUY" if pos.direction == 1 else "SELL", "signal_ts": _iso(bars.t[pos.signal_idx]),
                    "entry_ts": _iso(bars.t[pos.entry_idx]), "entry_price": float(pos.entry_price),
                    "exit_ts": _iso(bars.t[i]), "exit_price": float(px), "exit_reason": reason,
                    "stop_loss": float(pos.stop), "take_profit": pos.target, "units": float(pos.units),
                    "pnl": float(pnl), "r_multiple": float(pnl / risk_cash) if risk_cash > 0 else 0.0,
                    # commissions + spread/slippage actually paid: all of it on entry; on exit only for stop/time/data-end
                    # fills (a limit target needs mid to reach TP + half spread, so no extra exit spread is charged)
                    "costs": float(exit_comm + pos.entry_costs + entry_slip_cost
                                   + (0.0 if reason == "target" else (half + slip) * pos.units * cfg.contract_size)),
                    "bars_held": held,
                })
                pos = None
            mtm = (bars.c[i] - pos.entry_price) * pos.direction * pos.units * cfg.contract_size if pos else 0.0
            eq[i] = equity + mtm
        else:
            eq[i] = equity

        # 3) look for a new signal at the close of bar i (acted on at bar i+1's open)
        if pos is None and pending is None and i + 1 < n and i >= strategy.warmup and i % cfg.eval_every == 0:
            hour = int((bars.t[i] % 86400) // 3600)
            if cfg.allowed_hours_utc is None or hour in cfg.allowed_hours_utc:
                sig = strategy.signal(bars.upto(i + 1))
                if sig is not None:
                    pending = (i, sig)

    metrics = backtest_metrics(trades, eq, cfg.initial_equity, bars.step, n)
    curve = [[_iso(t), float(e)] for t, e in zip(bars.t, eq)]
    return BacktestResult(asdict(cfg), trades, curve, metrics, skipped,
                          {"strategy": strategy.name, "bars": n, "start": _iso(bars.t[0]) if n else None,
                           "end": _iso(bars.t[-1]) if n else None})

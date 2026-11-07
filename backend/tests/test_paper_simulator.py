"""Paper-trading execution model on hand-built candles (TEST FIXTURES ONLY)."""
import numpy as np
import pytest

from app.market_data.bars import Bars
from app.paper.simulator import CHASE_R, SimTrade, advance, build_path
from app.signals.execution import exit_on_candle, limit_touch, market_entry_ok

T0 = 1_740_996_000  # 2025-03-03 10:00 UTC, a minute boundary


def bars(rows: list[tuple[float, float, float, float]], start: int = T0, step: int = 60) -> Bars:
    n = len(rows)
    a = np.array(rows, dtype=float).reshape(n, 4)
    return Bars(t=np.arange(n, dtype=np.int64) * step + start, o=a[:, 0], h=a[:, 1], l=a[:, 2], c=a[:, 3], v=np.full(n, np.nan), step=step)


def buy(order_type: str = "market", entry: float = 100.0, sl: float = 95.0, tp: float = 110.0, detected: int = T0 - 30,
        valid: int = T0 + 3600, spread: float = 0.5, inv: float | None = 95.0) -> SimTrade:
    return SimTrade(d=1, order_type=order_type, entry=entry, sl=sl, tp=tp, inv=inv, spread=spread, detected_ts=detected,
                    valid_until_ts=valid, cursor_ts=detected)


def path(b: Bars, start: int | None = None):
    return build_path({"1m": b}, T0 - 30 if start is None else start)


# ---- shared execution rules ----
def test_execution_rules():
    assert limit_touch(1, 100, 110, high=111, low=101) == "missed"  # TP traded, entry untouched
    assert limit_touch(1, 100, 110, high=111, low=99) == "filled"  # both: the entry was touched
    assert limit_touch(-1, 100, 90, high=99, low=89) == "missed"
    assert limit_touch(1, 100, 110, high=105, low=101) is None
    assert exit_on_candle(1, 95, 110, 100, 111, 94) == (95, "stop")  # both levels in one candle: the stop
    assert exit_on_candle(1, 95, 110, 100, 111, 96) == (110, "target")
    assert exit_on_candle(1, 95, 110, 100, 111, 96, tp_allowed=False) is None
    assert exit_on_candle(1, 95, 110, 93, 96, 92, gap_fills=True) == (93, "stop")  # opened through the stop: filled at the open
    assert exit_on_candle(1, 95, 110, 93, 96, 92) == (95, "stop")  # replay rule: at the level
    assert exit_on_candle(-1, 105, 90, 88, 91, 87, gap_fills=True) == (88, "target")
    assert market_entry_ok(1, 100, 95, 110) and not market_entry_ok(1, 94, 95, 110) and not market_entry_ok(1, 111, 95, 110)


# ---- candle path ----
def test_path_prefers_1m_and_bridges_gaps_with_coarser_candles():
    one = bars([(100, 101, 99, 100)] * 5)  # 10:00-10:04
    five = bars([(100, 102, 98, 101)] * 6, step=300)  # 10:00-10:25
    p = build_path({"1m": one, "5m": five}, T0)
    assert [c[5] for c in p] == [60] * 5 + [300] * 5  # 1m first, then 5m candles from 10:05 on
    assert p[5][0] == T0 + 300
    late = build_path({"1m": one, "5m": five}, T0 + 90)  # starts inside the 10:01 candle: that candle is never used
    assert late[0][0] == T0 + 120


# ---- market orders ----
def test_market_order_fills_at_next_open_and_exits_at_target_net_of_spread():
    sim = advance(buy(), path(bars([(100.5, 103, 100, 102), (102, 111, 101, 109)])))
    assert sim.status == "closed" and sim.exit_reason == "target"
    assert sim.fill_price == 100.5 and sim.fill_ts == T0
    risk = 100.5 - 95
    assert sim.risk == pytest.approx(risk)
    assert sim.r_gross == pytest.approx((110 - 100.5) / risk)
    assert sim.r_net == pytest.approx((110 - 100.5) / risk - 0.5 / risk)
    assert sim.exit_ts == T0 + 60 and sim.mfe_r == pytest.approx(sim.r_gross)


def test_market_order_stop_wins_when_both_levels_trade_in_one_candle():
    sim = advance(buy(), path(bars([(100, 111, 94, 100)])))
    assert sim.status == "closed" and sim.exit_reason == "stop" and sim.r_gross == pytest.approx(-1.0)


def test_market_order_is_skipped_when_price_ran_away_or_gapped():
    chased = advance(buy(), path(bars([(100 + CHASE_R * 5 + 0.1, 104, 101, 103)])))
    assert chased.status == "skipped" and chased.exit_reason == "chased" and chased.fill_price is None
    gapped = advance(buy(), path(bars([(94, 96, 93, 95)])))
    assert gapped.status == "skipped" and gapped.exit_reason == "gapped"


def test_gap_through_the_stop_exits_at_the_open_not_the_stop():
    sim = advance(buy(), path(bars([(100, 101, 99, 100), (92, 93, 90, 91)])))
    assert sim.status == "closed" and sim.exit_price == 92 and sim.r_gross == pytest.approx(-8 / 5)


def test_open_position_is_marked_to_market_and_advancing_twice_changes_nothing():
    b = bars([(100, 102, 99, 101), (101, 103, 100, 102)])
    sim = advance(buy(), path(b))
    assert sim.status == "open" and sim.last_price == 102 and sim.cursor_ts == T0 + 120
    assert sim.unrealized_r() == pytest.approx(2 / 5 - 0.5 / 5)
    assert sim.mfe_r == pytest.approx(3 / 5) and sim.mae_r == pytest.approx(-1 / 5)
    again = advance(sim, path(b))
    assert again.status == "open" and again.cursor_ts == T0 + 120 and again.last_price == 102


# ---- limit orders ----
def test_limit_order_fill_candle_ignores_the_target_then_exits_later():
    b = bars([(103, 104, 102, 103), (102, 111, 99.5, 108), (108, 111, 107, 110)])  # 2nd candle touches entry AND TP
    sim = advance(buy("limit"), path(b))
    assert sim.status == "closed" and sim.fill_price == 100 and sim.fill_ts == T0 + 60
    assert sim.exit_ts == T0 + 120 and sim.exit_reason == "target"  # not on the fill candle


def test_limit_order_is_missed_when_tp1_trades_first():
    sim = advance(buy("limit"), path(bars([(103, 111, 101, 109)])))
    assert sim.status == "missed" and sim.exit_reason == "tp_before_fill" and sim.fill_price is None


def test_limit_order_is_cancelled_by_a_setup_close_beyond_invalidation():
    b = bars([(103, 104, 102, 103), (103, 104, 101, 102)])
    closes = [(T0 + 30, 94.0)]  # a setup candle closed below the invalidation 95 before the second 1m candle
    sim = advance(buy("limit"), path(b), closes)
    assert sim.status == "cancelled" and sim.exit_reason == "invalidated" and sim.exit_ts == T0 + 30


def test_pending_orders_expire_with_time_even_without_new_candles():
    sim = advance(buy("limit", valid=T0 + 120), [], now_ts=T0 + 200)
    assert sim.status == "expired" and sim.exit_ts == T0 + 120
    sell = SimTrade(d=-1, order_type="limit", entry=100, sl=105, tp=90, inv=105, spread=0.5, detected_ts=T0 - 30,
                    valid_until_ts=T0 + 600, cursor_ts=T0 - 30)
    sim2 = advance(sell, path(bars([(98, 101, 97, 100), (100, 100.5, 89, 90)])))
    assert sim2.status == "closed" and sim2.exit_reason == "target" and sim2.r_gross == pytest.approx(10 / 5)

"""Gann angles, fans and price-time balance (docs/gann/GANN_METHODOLOGY.md sections 4.3, 4.4)."""
import numpy as np

from app.gann.anchors import Anchor
from app.gann.angles import (
    LABEL,
    RATES,
    angle_events,
    balance_centres,
    fan,
    scale_atr,
    scale_swing,
)
from app.market_data.bars import Bars


def test_rates_and_labels():
    assert RATES == (1 / 8, 1 / 4, 1 / 3, 1 / 2, 1, 2, 3, 4, 8)
    assert LABEL[8] == "8x1" and LABEL[1 / 8] == "1x8" and LABEL[1] == "1x1" and LABEL[1 / 2] == "1x2"


def test_fan_rates():
    a = Anchor(10, 13, 100.0, "low", "major")
    f = fan(a, 2.0, np.array([4.0]))
    row = {r: f[k, 0] for k, r in enumerate(RATES)}
    assert row[1] == 108.0 and row[2] == 116.0 and row[1 / 2] == 104.0 and f.shape == (9, 1)


def test_down_fan_from_high():
    a = Anchor(0, 3, 200.0, "high", "major")
    assert fan(a, 2.0, np.array([5.0]), rates=(1,))[0, 0] == 190.0


def test_scale_swing_and_atr():
    prev, a = Anchor(0, 3, 100.0, "low", "major"), Anchor(25, 28, 150.0, "high", "major")
    assert scale_swing(prev, a) == 2.0
    assert scale_atr(np.arange(40, dtype=float), a) == 28.0


def test_balance_equals_1x1_identity():
    prev, a = Anchor(0, 3, 100.0, "low", "major"), Anchor(25, 28, 150.0, "high", "major")
    s = 3.0
    c_range, c_price = balance_centres(prev, a, s)
    assert c_range == 25 + 50 / 3 and c_price == 25 + 150 / 3
    one = fan(a, s, np.array([c_range - a.idx]), rates=(1,))[0, 0]
    assert abs(abs(one - a.price) - 50.0) < 1e-9  # squaring the range IS the 1x1 at the same scale


def test_angle_events_break_and_retest():
    n = 12
    line = 100.0 + np.arange(n)
    c = line + 2.0
    c[0] = 100.0
    c[6] = line[6] - 1.0
    c[7] = 106.6
    c[8:] = line[8:] - 3.0
    h, lo = c + 0.5, c - 0.5
    h[6], lo[6] = c[6] + 0.3, c[6] - 0.3
    h[7], lo[7] = 107.2, 106.5
    b = Bars(t=np.arange(n, dtype=np.int64) * 3600, o=c.copy(), h=h, l=lo, c=c, v=np.ones(n), step=3600)
    ev = angle_events(b, Anchor(0, 1, 100.0, "low", "major"), 1.0, 1, np.full(n, 0.1), start=1)
    assert np.flatnonzero(ev["touch"]).tolist() == [7]
    assert np.flatnonzero(ev["break_"]).tolist() == [6]
    assert np.flatnonzero(ev["retest"]).tolist() == [7]

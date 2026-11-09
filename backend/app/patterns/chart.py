"""Family G: classical chart patterns as geometry on confirmed swing pivots, with ATR tolerances (no subjective shapes).

Pivots: confirmed swings (standard 3 left / 3 right unless a definition says external 5 / 5) reduced, in order of confirmation, to an
alternating zigzag; a swing of the same kind as the last pivot replaces it only when it is more extreme. A formation is evaluated at
the candle T that confirms its last pivot, with ATR = ATR at T, and its event is the first breakout CLOSE at or after T. An event at
index i therefore uses candles 0..i and swings confirmed by i only.

Line patterns (triangles, wedges, channels, rectangle, broadening formation) use the last four pivots: the upper line runs through the
two pivot highs, the lower line through the two pivot lows. A line is flat when its two touches are within 0.5 ATR, rising / falling
when the later touch is more than 0.5 ATR higher / lower. Width ratio = distance between the lines at the last pivot / at the first
pivot: converging below 0.75, parallel 0.75-1.33. Every close from the first to the last pivot lies within 0.5 ATR of the lines and
the formation is at least 2 ATR high. A line pattern is live from T until the next pivot is confirmed (a newer formation then takes
over), the lines meet, or one pattern length after its last pivot. Neckline patterns (double / triple tops and bottoms, head and
shoulders) stay live until one pattern length after their last pivot or a newer formation of the same pattern. Any formation is void
once price trades beyond its stop before the breakout close.
"""
import math
from dataclasses import dataclass

import numpy as np

from app.market_structure.swings import Swing
from app.patterns.ctx import ChunkCtx, swing_arrays
from app.patterns.registry import Hits, Points, spec

TOL = 0.5  # ATR: flat line, equal double-top extremes, slack of the close-containment test
TOL_EXT = 1.0  # ATR: equal extremes on external (5/5) pivots (triple tops, head and shoulders) and cup rims
MIN_H = 2.0  # ATR: minimum height of a formation
POLE = 3.0  # ATR: minimum flag / pennant pole
DEPTH = 3.0  # ATR: minimum cup / saucer depth
CONV, PAR = 0.75, 1 / 0.75  # width ratio: converging below CONV, parallel within [CONV, PAR]
BOWL_MIN, BOWL_MAX, U_SHARE = 30, 300, 0.45  # cup / saucer length in candles, share of closes in the lower third of the depth

G = "G"
LINES = ("last four standard pivots; upper line through the two pivot highs, lower line through the two pivot lows; flat = the two "
         "touches within 0.5 ATR, rising / falling = more than 0.5 ATR apart; every close from the first to the last pivot within "
         "0.5 ATR of the lines; highest minus lowest pivot >= 2 ATR")
RATIO = "width ratio (distance between the lines at the last pivot / at the first pivot)"
LIVE = ("from the last pivot's confirmation until the next pivot is confirmed, the lines meet or one pattern length after the last "
        "pivot; void if price first trades beyond the stop")
BREAK = "the close beyond the line or level"
POLE_DEF = ("pole = standard pivot {a} P0 to pivot {b} P1, at least 3 ATR; flag = the next pivots P1 ({b}), {a}, {b}, {a} P4 with "
            "lines through its two highs and its two lows; the flag retraces at most 50% of the pole, lasts at most 3x the pole "
            "(P1 to P4) and every close from P1 to P4 lies within 0.5 ATR of its lines")
BOWL = ("lasts 30-300 candles, depth >= 3 ATR, its extreme lies in the middle half (25%-75%) of it and at least 45% of its closes "
        "lie in the third of the depth nearest the extreme (a U, not a V)")

spec(id="asc_triangle_breakout", family=G, name="Ascending Triangle", direction="bullish",
     definition=f"{LINES}; upper line flat, lower line rising; event = first close above the upper line {LIVE}",
     confirmation=BREAK, invalidation="the last pivot low")
spec(id="desc_triangle_breakdown", family=G, name="Descending Triangle", direction="bearish",
     definition=f"{LINES}; upper line falling, lower line flat; event = first close below the lower line {LIVE}",
     confirmation=BREAK, invalidation="the last pivot high")
spec(id="sym_triangle_breakout", family=G, name="Symmetrical Triangle (contracting triangle)", direction="both",
     definition=f"{LINES}; upper line falling, lower line rising; event = first close above the upper line (bullish) or below the "
                f"lower line (bearish) {LIVE}",
     confirmation=BREAK, invalidation="the last pivot low (bullish) / the last pivot high (bearish)")
spec(id="rising_wedge_breakdown", family=G, name="Rising Wedge", direction="bearish",
     definition=f"{LINES}; both lines rising, {RATIO} < 0.75 (converging); event = first close below the lower line {LIVE}",
     confirmation=BREAK, invalidation="the last pivot high")
spec(id="falling_wedge_breakout", family=G, name="Falling Wedge", direction="bullish",
     definition=f"{LINES}; both lines falling, {RATIO} < 0.75 (converging); event = first close above the upper line {LIVE}",
     confirmation=BREAK, invalidation="the last pivot low")
spec(id="rectangle_breakout", family=G, name="Rectangle (bullish breakout / bearish breakdown)", direction="both",
     definition=f"{LINES}; both lines flat; top = the higher pivot high, bottom = the lower pivot low; event = first close above the "
                f"top (bullish) or below the bottom (bearish) {LIVE}",
     confirmation=BREAK, invalidation="the last pivot low (bullish) / the last pivot high (bearish)")
spec(id="broadening_breakout", family=G, name="Broadening Formation (expanding triangle)", direction="both",
     definition=f"{LINES}; upper line rising, lower line falling (expanding); event = first close above the upper line (bullish) or "
                f"below the lower line (bearish) {LIVE}",
     confirmation=BREAK, invalidation="the last pivot low (bullish) / the last pivot high (bearish)")
spec(id="channel_breakout", family=G, name="Channel Breakout (with the channel)", direction="both",
     definition=f"{LINES}; both lines rising or both falling, {RATIO} 0.75-1.33 (parallel); event = first close above the upper "
                f"line of a rising channel (bullish) or below the lower line of a falling channel (bearish) {LIVE}",
     confirmation=BREAK, invalidation="the last pivot low (bullish) / the last pivot high (bearish)")
spec(id="rising_channel_break", family=G, name="Rising Channel (break of its support)", direction="bearish",
     definition=f"{LINES}; both lines rising, {RATIO} 0.75-1.33 (parallel); event = first close below the lower line {LIVE}",
     confirmation=BREAK, invalidation="the last pivot high")
spec(id="falling_channel_break", family=G, name="Falling Channel (break of its resistance)", direction="bullish",
     definition=f"{LINES}; both lines falling, {RATIO} 0.75-1.33 (parallel); event = first close above the upper line {LIVE}",
     confirmation=BREAK, invalidation="the last pivot low")
spec(id="bull_flag", family=G, name="Bullish Flag", direction="bullish",
     definition=f"{POLE_DEF.format(a='low', b='high')}; neither flag line rises more than 0.5 ATR and the width ratio (at P4 / at P1) "
                f"is 0.75-1.33 (parallel); event = first close above the upper flag line {LIVE}",
     confirmation=BREAK, invalidation="the last flag low (P4)")
spec(id="bear_flag", family=G, name="Bearish Flag", direction="bearish",
     definition=f"{POLE_DEF.format(a='high', b='low')}; neither flag line falls more than 0.5 ATR and the width ratio (at P4 / at P1) "
                f"is 0.75-1.33 (parallel); event = first close below the lower flag line {LIVE}",
     confirmation=BREAK, invalidation="the last flag high (P4)")
spec(id="bull_pennant", family=G, name="Bullish Pennant", direction="bullish",
     definition=f"{POLE_DEF.format(a='low', b='high')}; upper line falling, lower line rising, width ratio (at P4 / at P1) < 0.75 "
                f"(converging); event = first close above the upper line {LIVE}",
     confirmation=BREAK, invalidation="the last pennant low (P4)")
spec(id="bear_pennant", family=G, name="Bearish Pennant", direction="bearish",
     definition=f"{POLE_DEF.format(a='high', b='low')}; upper line falling, lower line rising, width ratio (at P4 / at P1) < 0.75 "
                f"(converging); event = first close below the lower line {LIVE}",
     confirmation=BREAK, invalidation="the last pennant high (P4)")
spec(id="double_top", family=G, name="Double Top", direction="bearish",
     definition="standard pivots L0, H1, N, H2 in a row (low, high, low, high): |H1 - H2| <= 0.5 ATR, min(H1, H2) - N >= 2 ATR, L0 "
                "below N (price rose into the pattern); event = first close below N from H2's confirmation, within one pattern "
                "length (H1 to H2) after H2 and before a newer double top; void if price first trades above max(H1, H2)",
     confirmation="the close below the neckline (the trough N)", invalidation="the higher of the two tops")
spec(id="double_bottom", family=G, name="Double Bottom", direction="bullish",
     definition="standard pivots H0, L1, N, L2 in a row (high, low, high, low): |L1 - L2| <= 0.5 ATR, N - max(L1, L2) >= 2 ATR, H0 "
                "above N (price fell into the pattern); event = first close above N from L2's confirmation, within one pattern "
                "length (L1 to L2) after L2 and before a newer double bottom; void if price first trades below min(L1, L2)",
     confirmation="the close above the neckline (the peak N)", invalidation="the lower of the two bottoms")
spec(id="triple_top", family=G, name="Triple Top", direction="bearish",
     definition="external (5/5) pivots L0, H1, N1, H2, N2, H3 in a row: max - min of the three highs <= 1 ATR, lowest high - "
                "max(N1, N2) >= 2 ATR, L0 below min(N1, N2); event = first close below min(N1, N2) from H3's confirmation, within "
                "one pattern length (H1 to H3) after H3 and before a newer triple top; void if price first trades above the highest top",
     confirmation="the close below the neckline (the lower trough)", invalidation="the highest of the three tops")
spec(id="triple_bottom", family=G, name="Triple Bottom", direction="bullish",
     definition="external (5/5) pivots H0, L1, N1, L2, N2, L3 in a row: max - min of the three lows <= 1 ATR, min(N1, N2) - highest "
                "low >= 2 ATR, H0 above max(N1, N2); event = first close above max(N1, N2) from L3's confirmation, within one "
                "pattern length (L1 to L3) after L3 and before a newer triple bottom; void if price first trades below the lowest bottom",
     confirmation="the close above the neckline (the higher peak)", invalidation="the lowest of the three bottoms")
spec(id="head_and_shoulders", family=G, name="Head and Shoulders", direction="bearish",
     definition="external (5/5) pivots L0, LS, N1, HD, N2, RS in a row (low, high, ...): HD > max(LS, RS) + 1 ATR, |LS - RS| <= 1 "
                "ATR, |N1 - N2| <= 1 ATR, min(LS, RS) - max(N1, N2) >= 1 ATR, L0 below min(N1, N2), no close from LS to RS more "
                "than 0.5 ATR below the neckline (line through N1 and N2); event = first close below the neckline from RS's "
                "confirmation, within one pattern length (LS to RS) after RS and before a newer one; void if price first trades "
                "above the head",
     confirmation="the close below the neckline", invalidation="the head")
spec(id="inverse_head_and_shoulders", family=G, name="Inverse Head and Shoulders", direction="bullish",
     definition="external (5/5) pivots H0, LS, N1, HD, N2, RS in a row (high, low, ...): HD < min(LS, RS) - 1 ATR, |LS - RS| <= 1 "
                "ATR, |N1 - N2| <= 1 ATR, min(N1, N2) - max(LS, RS) >= 1 ATR, H0 above max(N1, N2), no close from LS to RS more "
                "than 0.5 ATR above the neckline (line through N1 and N2); event = first close above the neckline from RS's "
                "confirmation, within one pattern length (LS to RS) after RS and before a newer one; void if price first trades "
                "below the head",
     confirmation="the close above the neckline", invalidation="the head")
spec(id="cup_and_handle", family=G, name="Cup and Handle", direction="bullish",
     definition=f"rims = external (5/5) swing highs R1 then R2, R1 being the most recent external swing high at or above R2 - 1 ATR "
                f"(within 300 candles): R1 - R2 <= 1 ATR, no high between them above max(R1, R2); the cup (R1 to R2, depth = "
                f"min(R1, R2) - its lowest low) {BOWL}; event = first close above R2 within half the cup's length after R2, "
                f"provided no low after R2 reached the lower half of the cup (the handle)",
     confirmation="the close above the right rim", invalidation="the handle low (lowest low from the right rim to the breakout)")
spec(id="inverse_cup_and_handle", family=G, name="Inverse Cup and Handle", direction="bearish",
     definition=f"rims = external (5/5) swing lows R1 then R2, R1 being the most recent external swing low at or below R2 + 1 ATR "
                f"(within 300 candles): R2 - R1 <= 1 ATR, no low between them below min(R1, R2); the inverted cup (R1 to R2, depth "
                f"= its highest high - max(R1, R2)) {BOWL}; event = first close below R2 within half the cup's length after R2, "
                f"provided no high after R2 reached the upper half of the cup (the handle)",
     confirmation="the close below the right rim", invalidation="the handle high (highest high from the right rim to the breakdown)")
spec(id="rounding_bottom", family=G, name="Rounding Bottom (saucer)", direction="bullish",
     definition=f"rim = an external (5/5) swing high R; event = the first close above R, provided the saucer from R to that close "
                f"(depth = R - its lowest low) {BOWL}",
     confirmation="the close above the rim",
     invalidation="the most recent confirmed 3/3 swing low at or after the saucer's lowest low (that low itself if none)")
spec(id="rounding_top", family=G, name="Rounding Top", direction="bearish",
     definition=f"rim = an external (5/5) swing low R; event = the first close below R, provided the dome from R to that close "
                f"(depth = its highest high - R) {BOWL}",
     confirmation="the close below the rim",
     invalidation="the most recent confirmed 3/3 swing high at or after the dome's highest high (that high itself if none)")
for pid, nm, why in (
    ("rectangle_directional", "Bullish Rectangle Breakout / Bearish Rectangle Breakdown",
     "identical to rectangle_breakout (its bullish and bearish sides)"),
    ("contracting_triangle", "Contracting Triangle",
     "identical to sym_triangle_breakout (the right-angled contracting variants are asc_triangle_breakout / desc_triangle_breakdown)"),
    ("expanding_triangle", "Expanding Triangle", "identical to broadening_breakout"),
    ("diamond_top", "Diamond Top",
     "a broadening phase then a contracting phase (pivots H1 < H2 > H3 with L1 > L2 < L3) is the same pivot sequence as a head and "
     "shoulders with a sloping neckline, so no objective rule separates it, and it is too rare on 3/3 or 5/5 swings to test alone"),
    ("diamond_bottom", "Diamond Bottom",
     "the mirror of diamond_top: same pivot sequence as an inverse head and shoulders with a sloping neckline, and too rare to test"),
):
    spec(id=pid, family=G, name=nm, direction="both", definition="-", status="scoped_out", reason=why)


@dataclass(frozen=True, slots=True)
class _Pv:
    idx: int
    k: int  # +1 pivot high, -1 pivot low
    price: float


def _zigzag(swings: list[Swing], n: int) -> list[tuple[int, tuple[_Pv, ...]]]:
    """(T, last six pivots) after every change of the alternating pivot sequence; T = the candle that confirmed the change."""
    piv: list[_Pv] = []
    out = []
    for s in sorted(swings, key=lambda s: (s.confirm_idx, s.idx)):
        if s.confirm_idx >= n:
            continue
        p = _Pv(s.idx, 1 if s.kind == "high" else -1, float(s.price))
        if piv and piv[-1].k == p.k:
            if p.k * (p.price - piv[-1].price) <= 0:
                continue  # not more extreme than the pivot it would replace
            piv[-1] = p
        else:
            piv.append(p)
        out.append((s.confirm_idx, tuple(piv[-6:])))
    return out


def _line(p: _Pv, q: _Pv) -> tuple[float, float]:
    """(intercept, slope) of the line through two pivots, as price = a + b * candle index."""
    b = (q.price - p.price) / (q.idx - p.idx)
    return p.price - b * p.idx, b


def _cls(d: float, atr: float) -> int:
    return 0 if abs(d) <= TOL * atr else 1 if d > 0 else -1


def _apex(aU: float, bU: float, aL: float, bL: float) -> int:
    """Last candle before the two lines meet (a large number when they do not converge)."""
    if bL - bU <= 0:
        return 1 << 60
    return math.ceil((aU - aL) / (bL - bU)) - 1


class _Det:
    def __init__(self, ctx: ChunkCtx) -> None:
        self.ctx, self.n = ctx, ctx.n
        self.c, self.h, self.l, self.atr = (np.asarray(x, dtype=float) for x in (ctx.c, ctx.h, ctx.l, ctx.atr))
        self.P = Points()
        self.seen: set[tuple[str, int, int]] = set()

    def atr_at(self, i: int) -> float:
        a = float(self.atr[i])
        return a if a > 0 else 0.0  # NaN during the ATR warm-up

    def put(self, pid: str, j: int, d: int, stop: float) -> None:
        if not (stop < self.c[j] if d > 0 else stop > self.c[j]):
            return
        if (pid, j, d) not in self.seen:
            self.seen.add((pid, j, d))
            self.P.put(pid, j, d, stop)

    def inside(self, i0: int, i1: int, lo, hi, slack: float) -> bool:
        """Every close of candles i0..i1 no more than `slack` below the line lo / above the line hi (either may be None)."""
        js = np.arange(i0, i1 + 1)
        cc = self.c[i0:i1 + 1]
        if lo is not None and (cc < lo[0] + lo[1] * js - slack).any():
            return False
        return not (hi is not None and (cc > hi[0] + hi[1] * js + slack).any())

    def first_close(self, j0: int, j1: int, d: int, a: float, b: float, stop: float, k0: int) -> int:
        """First j in [j0, j1] closing beyond the line a + b*j (above when d > 0), unless a candle in [k0, j] traded beyond stop."""
        if j1 < j0:
            return -1
        bad = np.flatnonzero(self.l[k0:j1 + 1] < stop) if d > 0 else np.flatnonzero(self.h[k0:j1 + 1] > stop)
        if len(bad):
            j1 = min(j1, k0 + int(bad[0]) - 1)
            if j1 < j0:
                return -1
        line = a + b * np.arange(j0, j1 + 1)
        cc = self.c[j0:j1 + 1]
        hit = np.flatnonzero(cc > line if d > 0 else cc < line)
        return j0 + int(hit[0]) if len(hit) else -1

    def scan(self, sides, j0: int, j1: int, k0: int) -> None:
        """Report the earliest breakout among the sides (pid, direction, a, b, stop) of one formation."""
        best = None
        for pid, d, a, b, stop in sides:
            j = self.first_close(j0, j1, d, a, b, stop, k0)
            if j >= 0 and (best is None or j < best[1]):
                best = (pid, j, d, stop)
        if best:
            self.put(*best)

    # line patterns and flags: standard pivots, live until the next pivot -------------------------------------------------------
    def lines(self, zz) -> None:
        for k, (T, piv) in enumerate(zz):
            t_next = zz[k + 1][0] if k + 1 < len(zz) else self.n - 1
            A = self.atr_at(T)
            if not A:
                continue
            if len(piv) >= 4:
                self._channel(piv[-4:], T, t_next, A)
            if len(piv) >= 5:
                self._flag(piv[-5:], T, t_next, A)

    def _channel(self, w, T: int, t_next: int, A: float) -> None:
        (h1, h2), (l1, l2) = [p for p in w if p.k > 0], [p for p in w if p.k < 0]
        aU, bU = _line(h1, h2)
        aL, bL = _line(l1, l2)
        i0, i1 = w[0].idx, w[-1].idx
        w0, w1 = aU - aL + (bU - bL) * i0, aU - aL + (bU - bL) * i1
        if w0 <= 0 or w1 <= 0 or max(h1.price, h2.price) - min(l1.price, l2.price) < MIN_H * A:
            return
        su, sl, r = _cls(h2.price - h1.price, A), _cls(l2.price - l1.price, A), w1 / w0
        up = lambda pid: (pid, 1, aU, bU, l2.price)  # noqa: E731  (long: break of the upper line, stop at the last pivot low)
        dn = lambda pid: (pid, -1, aL, bL, h2.price)  # noqa: E731
        if (su, sl) == (0, 0):
            sides = [("rectangle_breakout", 1, max(h1.price, h2.price), 0.0, l2.price),
                     ("rectangle_breakout", -1, min(l1.price, l2.price), 0.0, h2.price)]
        elif (su, sl) == (0, 1):
            sides = [up("asc_triangle_breakout")]
        elif (su, sl) == (-1, 0):
            sides = [dn("desc_triangle_breakdown")]
        elif (su, sl) == (-1, 1):
            sides = [up("sym_triangle_breakout"), dn("sym_triangle_breakout")]
        elif (su, sl) == (1, -1):
            sides = [up("broadening_breakout"), dn("broadening_breakout")]
        elif su == sl == 1:
            sides = [dn("rising_wedge_breakdown")] if r < CONV else [up("channel_breakout"), dn("rising_channel_break")] if r <= PAR else []
        elif su == sl == -1:
            sides = [up("falling_wedge_breakout")] if r < CONV else [up("falling_channel_break"), dn("channel_breakout")] if r <= PAR else []
        else:
            return
        if not sides or not self.inside(i0, i1, (aL, bL), (aU, bU), TOL * A):
            return
        self.scan(sides, T, min(t_next, i1 + (i1 - i0), self.n - 1, _apex(aU, bU, aL, bL)), i1 + 1)

    def _flag(self, w, T: int, t_next: int, A: float) -> None:
        p0, p1, p2, p3, p4 = w
        d = 1 if p0.k < 0 else -1  # pole up from a low: bullish
        pole, pole_len, flag_len = d * (p1.price - p0.price), p1.idx - p0.idx, p4.idx - p1.idx
        if pole < POLE * A or pole_len <= 0 or flag_len > 3 * pole_len:
            return
        if d > 0:
            (h1, h2), (l1, l2), retr = (p1, p3), (p2, p4), p1.price - min(p2.price, p4.price)
        else:
            (l1, l2), (h1, h2), retr = (p1, p3), (p2, p4), max(p2.price, p4.price) - p1.price
        if retr > 0.5 * pole:
            return
        aU, bU = _line(h1, h2)
        aL, bL = _line(l1, l2)
        w0, w1 = aU - aL + (bU - bL) * p1.idx, aU - aL + (bU - bL) * p4.idx
        if w0 <= 0 or w1 <= 0:
            return
        r, du, dl = w1 / w0, h2.price - h1.price, l2.price - l1.price
        if CONV <= r <= PAR and d * du <= TOL * A and d * dl <= TOL * A:
            pid = "bull_flag" if d > 0 else "bear_flag"
        elif r < CONV and du < 0 < dl:
            pid = "bull_pennant" if d > 0 else "bear_pennant"
        else:
            return
        if not self.inside(p1.idx, p4.idx, (aL, bL), (aU, bU), TOL * A):
            return
        side = (pid, d, aU, bU, p4.price) if d > 0 else (pid, d, aL, bL, p4.price)
        self.scan([side], T, min(t_next, p4.idx + flag_len, self.n - 1, _apex(aU, bU, aL, bL)), p4.idx + 1)

    # neckline patterns: live until one pattern length after the last pivot or a newer formation of the same pattern ------------
    def necklines(self, zz_std, zz_ext) -> None:
        cands: dict[str, list] = {}
        for T, piv in zz_std:
            A = self.atr_at(T)
            if A and len(piv) >= 4:
                self._double(piv[-4:], T, A, cands)
        for T, piv in zz_ext:
            A = self.atr_at(T)
            if A and len(piv) >= 6:
                self._triple_hs(piv[-6:], T, A, cands)
        for pid, L in cands.items():
            for i, (T, j_exp, d, a, b, stop, k0) in enumerate(L):
                j1 = min(j_exp, self.n - 1, L[i + 1][0] - 1 if i + 1 < len(L) else self.n)
                self.scan([(pid, d, a, b, stop)], T, j1, k0)

    def _double(self, w, T: int, A: float, cands: dict) -> None:
        p0, p1, p2, p3 = w
        s = p3.k  # +1: two tops, -1: two bottoms (prices times s turn bottoms into tops)
        v0, v1, v2, v3 = (s * p.price for p in w)
        if abs(v1 - v3) > TOL * A or min(v1, v3) - v2 < MIN_H * A or not v0 < v2:
            return
        cands.setdefault("double_top" if s > 0 else "double_bottom", []).append(
            (T, p3.idx + (p3.idx - p1.idx), -s, p2.price, 0.0, s * max(v1, v3), p3.idx + 1))

    def _triple_hs(self, w, T: int, A: float, cands: dict) -> None:
        p1, p2, p3, p4, p5 = w[1:]
        s = p5.k
        v = [s * p.price for p in w]
        tops, necks = (v[1], v[3], v[5]), (v[2], v[4])
        if not v[0] < min(necks):
            return
        span = p5.idx - p1.idx
        if max(tops) - min(tops) <= TOL_EXT * A and min(tops) - max(necks) >= MIN_H * A:
            cands.setdefault("triple_top" if s > 0 else "triple_bottom", []).append(
                (T, p5.idx + span, -s, s * min(necks), 0.0, s * max(tops), p5.idx + 1))
        elif (v[3] - max(v[1], v[5]) > TOL_EXT * A and abs(v[1] - v[5]) <= TOL_EXT * A and abs(v[2] - v[4]) <= TOL_EXT * A
              and min(v[1], v[5]) - max(necks) >= TOL_EXT * A):
            a, b = _line(p2, p4)
            neck = (a, b)
            if self.inside(p1.idx, p5.idx, neck if s > 0 else None, None if s > 0 else neck, TOL * A):
                cands.setdefault("head_and_shoulders" if s > 0 else "inverse_head_and_shoulders", []).append(
                    (T, p5.idx + span, -s, a, b, p3.price, p5.idx + 1))

    # bowls: rounding bottom / top and cup and handle on external swings ----------------------------------------------------------
    def _bowl_ok(self, a: int, e: int, d: int, rim: float, A: float):
        """Extreme index and price of the bowl strictly between candles a and e if it is a U of the required depth, else None."""
        inner = slice(a + 1, e)
        m = a + 1 + int(np.argmin(self.l[inner]) if d > 0 else np.argmax(self.h[inner]))
        ext = self.l[m] if d > 0 else self.h[m]
        depth = d * (rim - ext)
        if depth < DEPTH * A or not 0.25 <= (m - a) / (e - a) <= 0.75:
            return None
        if np.mean(d * (self.c[inner] - ext) <= depth / 3) < U_SHARE:
            return None
        return m, float(ext), depth

    def saucers(self) -> None:
        n, c = self.n, self.c
        arrs = {k: swing_arrays(self.ctx.swings, k) for k in ("high", "low")}
        for s in self.ctx.swings_ext:
            if s.confirm_idx >= n:
                continue
            d = 1 if s.kind == "high" else -1  # a swing-high rim makes a rounding bottom (bullish)
            a, rim = s.idx, s.price
            seg = c[a + 1:min(n, a + BOWL_MAX + 1)]
            hit = np.flatnonzero(seg > rim if d > 0 else seg < rim)
            if not len(hit):
                continue
            j = a + 1 + int(hit[0])
            A = self.atr_at(j)
            if j - a < BOWL_MIN or j < s.confirm_idx or not A:
                continue
            bowl = self._bowl_ok(a, j, d, rim, A)
            if bowl is None:
                continue
            m, ext, _ = bowl
            si, sp, sc = arrs["low" if d > 0 else "high"]
            k = np.flatnonzero((si >= m) & (si < j) & (sc <= j))
            stop = float(sp[k[np.argmax(si[k])]]) if len(k) else ext
            self.put("rounding_bottom" if d > 0 else "rounding_top", j, d, stop)

    def cups(self) -> None:
        n, c = self.n, self.c
        for kind, d in (("high", 1), ("low", -1)):
            rims = [s for s in self.ctx.swings_ext if s.kind == kind and s.confirm_idx < n]
            for r, s2 in enumerate(rims):
                b, p2 = s2.idx, s2.price
                A = self.atr_at(s2.confirm_idx)
                if not A:
                    continue
                s1 = None
                for q in range(r - 1, -1, -1):
                    if b - rims[q].idx > BOWL_MAX:
                        break
                    if d * (rims[q].price - p2) >= -TOL_EXT * A:
                        s1 = rims[q]
                        break
                if s1 is None:
                    continue
                a, p1 = s1.idx, s1.price
                if d * (p1 - p2) > TOL_EXT * A or b - a < BOWL_MIN:
                    continue
                if (self.h[a + 1:b].max() >= max(p1, p2)) if d > 0 else (self.l[a + 1:b].min() <= min(p1, p2)):
                    continue
                bowl = self._bowl_ok(a, b, d, min(p1, p2) if d > 0 else max(p1, p2), A)
                if bowl is None:
                    continue
                _, ext, depth = bowl
                seg = c[b + 1:min(n, b + (b - a) // 2 + 1)]
                hit = np.flatnonzero(seg > p2 if d > 0 else seg < p2)
                if not len(hit):
                    continue
                j = b + 1 + int(hit[0])
                if j <= s2.confirm_idx:
                    continue
                handle = float(self.l[b + 1:j].min() if d > 0 else self.h[b + 1:j].max())
                if d * (handle - ext) < depth / 2:
                    continue
                self.put("cup_and_handle" if d > 0 else "inverse_cup_and_handle", j, d, handle)


def detect(ctx: ChunkCtx) -> Hits:
    D = _Det(ctx)
    if ctx.n >= 20:
        zz_std = _zigzag(ctx.swings, ctx.n)
        D.lines(zz_std)
        D.necklines(zz_std, _zigzag(ctx.swings_ext, ctx.n))
        D.saucers()
        D.cups()
    return D.P.flush(Hits())

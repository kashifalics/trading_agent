"""Family I: Fibonacci and harmonic patterns on a causal zigzag of confirmed swings.

Zigzag: the platform's standard swings (3 left / 3 right, ctx.swings) taken in order of confirmation. Pivots alternate high / low: a
swing of the same kind as the last pivot replaces it only when it is more extreme (otherwise it is ignored), and a swing of the other
kind that does not go beyond the last pivot (a low above the last high, a high below the last low) is ignored, so every leg has a
positive length. A pattern is evaluated each time its last pivot is added or replaced, at the candle that CONFIRMS that pivot (its
confirm_idx = pivot + 3), never at the extreme itself, and each pattern fires at most once per set of earlier pivots (a deeper D after
a hit does not fire again). An event at index i therefore uses candles 0..i and swings confirmed by i only.

Ratios are measured on swing prices. For X-A-B-C-D: AB/XA = |A-B| / |A-X| (B's retracement of XA), BC/AB = |C-B| / |A-B|,
CD/BC = |C-D| / |C-B|, AD/XA = |A-D| / |A-X| (D's retracement of XA; above 1 = beyond X), XC = |C-D| / |C-X| (D's retracement of XC).
A published ratio range lo-hi is accepted with a 5% tolerance: lo x 0.95 <= ratio <= hi x 1.05 (a single value r: 0.95 r to 1.05 r).
Direction: bullish when the last pivot (D) is a swing low, bearish when it is a swing high, unless a definition says otherwise.
ATR = 14-candle Wilder ATR at the pivot named.
"""
import numpy as np

from app.patterns.ctx import ChunkCtx
from app.patterns.registry import Hits, Points, spec

TOL = 0.05  # relative tolerance on every published harmonic ratio
IMPULSE_ATR = 3.0  # Fibonacci families: minimum impulse leg
EXT_LEVEL, EXT_WINDOW, EXT_RETR = 1.272, 50, (0.236, 0.886)
FIB_BANDS = {"fib_retracement": (0.382, 0.5), "golden_pullback": (0.588, 0.648), "deep_retracement": (0.786, 0.886)}
STOP_FRAC = 0.25  # stop beyond D by this fraction of the reference leg
IMPULSE_MIN_ATR, WAVE5_MIN_ATR = 5.0, 4.0  # Elliott-inspired structures: minimum size

# id: (name, ratio constraints, stop rule: "x" = beyond X, "d" = D -/+ 0.25 |XA|)
HARMONICS: dict[str, tuple[str, dict[str, tuple[float, float]], str]] = {
    "gartley": ("Gartley", {"ab_xa": (0.618, 0.618), "bc_ab": (0.382, 0.886), "cd_bc": (1.13, 1.618), "ad_xa": (0.786, 0.786)}, "x"),
    "bat": ("Bat", {"ab_xa": (0.382, 0.5), "bc_ab": (0.382, 0.886), "cd_bc": (1.618, 2.618), "ad_xa": (0.886, 0.886)}, "x"),
    "butterfly": ("Butterfly", {"ab_xa": (0.786, 0.786), "bc_ab": (0.382, 0.886), "cd_bc": (1.618, 2.24), "ad_xa": (1.27, 1.27)}, "d"),
    "crab": ("Crab", {"ab_xa": (0.382, 0.618), "bc_ab": (0.382, 0.886), "cd_bc": (2.24, 3.618), "ad_xa": (1.618, 1.618)}, "d"),
    "deep_crab": ("Deep Crab", {"ab_xa": (0.886, 0.886), "bc_ab": (0.382, 0.886), "cd_bc": (2.0, 3.618), "ad_xa": (1.618, 1.618)}, "d"),
    "cypher": ("Cypher", {"ab_xa": (0.382, 0.618), "bc_ab": (1.13, 1.414), "xc": (0.786, 0.786)}, "x"),
    "shark": ("Shark", {"bc_ab": (1.13, 1.618), "cd_bc": (1.618, 2.24), "ad_xa": (0.886, 1.13)}, "d"),
}
LABEL = {"ab_xa": "AB/XA", "bc_ab": "BC/AB", "cd_bc": "CD/BC", "ad_xa": "AD/XA", "xc": "D's retracement of XC"}
ABCD = {"bc_ab": (0.382, 0.886), "cd_ab": (1.0, 1.0)}
DRIVES = {"retr": (0.618, 0.786), "ext": (1.272, 1.618)}
WAVE4_RETR = (0.236, 0.618)

FAM = "I"
ZZ = "five consecutive zigzag pivots X-A-B-C-D"
TOL_TXT = "each ratio within 5% of the published value or range"


def _r(lo_hi: tuple[float, float]) -> str:
    lo, hi = lo_hi
    return f"{lo:g}" if lo == hi else f"{lo:g}-{hi:g}"


def _ratios_txt(cons: dict) -> str:
    return ", ".join(f"{LABEL[k]} = {_r(v)}" for k, v in cons.items())


FIB_TXT = ("after an impulse leg A-B between two consecutive zigzag pivots of at least 3 ATR (ATR at B), the first confirmed "
           "counter-swing C retraces {band} of it (leg B-C / leg A-B, in price, no extra tolerance); event at C's confirmation, in the impulse's "
           "direction (bullish after an up leg)")
for pid, nm, band in (("fib_retracement", "Fibonacci Retracement (0.382-0.5)", "0.382-0.5"),
                      ("golden_pullback", "Golden Ratio Pullback (0.618)", "0.588-0.648 (0.618 +/- 0.03)"),
                      ("deep_retracement", "Deep Retracement (0.786-0.886)", "0.786-0.886")):
    spec(id=pid, family=FAM, name=nm, direction="both", definition=FIB_TXT.format(band=band),
         confirmation="the candle that confirms the counter-swing C", invalidation="the counter-swing pivot C (pullback low / high)")
spec(id="fib_extension", family=FAM, name="Fibonacci Extension (1.272 continuation)", direction="both",
     definition="after an impulse leg A-B of at least 3 ATR (ATR at B) and a first confirmed counter-swing C retracing 0.236-0.886 of "
                "it, the first close within 50 candles of C's confirmation (from that candle on) beyond the 1.272 extension of the "
                "impulse (A + 1.272 x (B - A)), with no close beyond C before it; direction of the impulse (continuation). One event "
                "per impulse: the 1.618 level is a later point of the same move and is not a separate event",
     confirmation="the close beyond the 1.272 extension", invalidation="the counter-swing pivot C")
spec(id="abcd", family=FAM, name="AB=CD", direction="both",
     definition=f"four consecutive zigzag pivots A-B-C-D: BC/AB = {_r(ABCD['bc_ab'])} and CD/AB = 1.0 ({TOL_TXT}); event at D's "
                "confirmation",
     confirmation="the candle that confirms D", invalidation="beyond D by 0.25 x the AB leg (D - 0.25 AB bullish, D + 0.25 AB bearish)")
for pid, (nm, cons, stop) in HARMONICS.items():
    extra = {"cypher": "; C lies beyond A", "shark": "; C lies beyond A, AB/XA unconstrained"}.get(pid, "")
    spec(id=pid, family=FAM, name=nm, direction="both",
         definition=f"{ZZ}: {_ratios_txt(cons)}{extra} ({TOL_TXT}); event at D's confirmation (Carney-style published ratios)",
         confirmation="the candle that confirms D",
         invalidation="X, the pattern's origin, which lies beyond D" if stop == "x"
         else "beyond D by 0.25 x the XA leg (D - 0.25 XA bullish, D + 0.25 XA bearish)")
spec(id="three_drives", family=FAM, name="Three Drives", direction="both",
     definition="six consecutive zigzag pivots S-D1-C1-D2-C2-D3: each correction retraces 0.618-0.786 of the drive before it "
                "(legs D1-C1 / S-D1 and D2-C2 / C1-D2) and drives 2 and 3 extend 1.272-1.618 of the correction before them "
                f"(legs C1-D2 / D1-C1 and C2-D3 / D2-C2) ({TOL_TXT}); event at D3's confirmation; bearish after three drives "
                "up, bullish after three drives down",
     confirmation="the candle that confirms D3", invalidation="beyond D3 by 0.25 x the C2-D3 leg")
spec(id="elliott_impulse", family=FAM, name="Elliott Wave-inspired completed 5-wave impulse", direction="both",
     definition="six consecutive zigzag pivots P0..P5 (waves 1-5) obeying the three Elliott rules: wave 2 does not retrace beyond "
                "P0, wave 3 is not the shortest of waves 1, 3, 5, wave 4 does not enter wave 1's territory (P4 beyond P1); also P3 "
                "beyond P1 and P5 beyond P3, and the P0-P5 move >= 5 ATR (ATR at P5); event at P5's confirmation, direction AGAINST the "
                "impulse (the corrective phase the theory expects); an Elliott-inspired swing rule, not a wave count",
     confirmation="the candle that confirms P5", invalidation="P5, the impulse extreme")
spec(id="elliott_wave5", family=FAM, name="Elliott Wave-inspired wave-5 setup (end of wave 4)", direction="both",
     definition="five consecutive zigzag pivots P0..P4 (waves 1-4): wave 2 does not retrace beyond P0, P3 beyond P1, wave 3 longer "
                "than wave 1 (so it cannot be the shortest whatever wave 5 does), wave 4 does not enter wave 1's territory (P4 beyond "
                "P1) and retraces 0.236-0.618 of wave 3 (within 5%), the P0-P3 move >= 4 ATR (ATR at P4); event at P4's confirmation, in "
                "the impulse's direction (wave 5 expected); an Elliott-inspired swing rule, not a wave count",
     confirmation="the candle that confirms P4", invalidation="P1 (wave 4 crossing it breaks the count)")


def _ok(x: float, lo_hi: tuple[float, float]) -> bool:
    return lo_hi[0] * (1 - TOL) <= x <= lo_hi[1] * (1 + TOL)


def _zigzag(swings):
    """Yield (pivots, appended) after every swing that changes the zigzag; pivot = (idx, +1 high / -1 low, price, confirm_idx)."""
    piv: list[tuple[int, int, float, int]] = []
    for s in sorted(swings, key=lambda s: (s.confirm_idx, s.idx)):
        k = 1 if s.kind == "high" else -1
        p = (s.idx, k, float(s.price), s.confirm_idx)
        if piv and piv[-1][1] == k:
            if k * (p[2] - piv[-1][2]) <= 0:
                continue  # not more extreme than the pivot it would replace
            piv[-1] = p
            yield piv, False
        else:
            if piv and k * (p[2] - piv[-1][2]) <= 0:
                continue  # does not go beyond the last pivot
            piv.append(p)
            yield piv, True


class _Det:
    def __init__(self, ctx: ChunkCtx) -> None:
        self.n = ctx.n
        self.c = np.asarray(ctx.c, dtype=float)
        self.atr = np.asarray(ctx.atr, dtype=float)
        self.P = Points()
        self.fired: set[tuple] = set()

    def once(self, pid: str, piv, k: int) -> bool:
        """True the first time pid fires on these earlier pivots (the last k-1 pivots before D)."""
        key = (pid,) + tuple(p[0] for p in piv[-k:-1])
        if key in self.fired:
            return False
        self.fired.add(key)
        return True

    def fib(self, piv, i: int) -> None:
        (_, _, a, _), (ib, kb, b, _), (_, _, cc, conf) = piv[-3:]
        d = kb  # impulse up when B is a high
        imp, ret = d * (b - a), d * (b - cc)
        if not imp >= IMPULSE_ATR * self.atr[ib]:
            return
        r = ret / imp
        for pid, band in FIB_BANDS.items():
            if band[0] <= r <= band[1]:
                self.P.put(pid, i, d, cc)
        if EXT_RETR[0] <= r <= EXT_RETR[1]:
            level = a + EXT_LEVEL * (b - a)
            seg = d * self.c[conf:min(self.n, conf + EXT_WINDOW + 1)]
            hit, lost = np.flatnonzero(seg > d * level), np.flatnonzero(seg < d * cc)
            if len(hit) and (not len(lost) or hit[0] < lost[0]):
                self.P.put("fib_extension", conf + int(hit[0]), d, cc)

    def abcd(self, piv, i: int) -> None:
        d = -piv[-1][1]
        ya, yb, yc, yd = (d * p[2] for p in piv[-4:])
        ab = ya - yb
        if _ok((yc - yb) / ab, ABCD["bc_ab"]) and _ok((yc - yd) / ab, ABCD["cd_ab"]) and self.once("abcd", piv, 4):
            self.P.put("abcd", i, d, piv[-1][2] - d * STOP_FRAC * ab)

    def xabcd(self, piv, i: int) -> None:
        d = -piv[-1][1]
        yx, ya, yb, yc, yd = (d * p[2] for p in piv[-5:])
        xa, ab, bc, cd = ya - yx, ya - yb, yc - yb, yc - yd
        r = {"ab_xa": ab / xa, "bc_ab": bc / ab, "cd_bc": cd / bc, "ad_xa": (ya - yd) / xa,
             "xc": cd / (yc - yx) if yc > yx else np.nan}
        for pid, (_, cons, stop) in HARMONICS.items():
            if all(_ok(r[k], v) for k, v in cons.items()) and self.once(pid, piv, 5):
                self.P.put(pid, i, d, piv[-5][2] if stop == "x" else piv[-1][2] - d * STOP_FRAC * xa)

    def three_drives(self, piv, i: int) -> None:
        d = -piv[-1][1]
        ys, y1, c1, y2, c2, y3 = (d * p[2] for p in piv[-6:])  # in y the drives point down
        if (_ok((c1 - y1) / (ys - y1), DRIVES["retr"]) and _ok((c1 - y2) / (c1 - y1), DRIVES["ext"])
                and _ok((c2 - y2) / (c1 - y2), DRIVES["retr"]) and _ok((c2 - y3) / (c2 - y2), DRIVES["ext"])
                and self.once("three_drives", piv, 6)):
            self.P.put("three_drives", i, d, piv[-1][2] - d * STOP_FRAC * (c2 - y3))

    def elliott_impulse(self, piv, i: int) -> None:
        u = piv[-1][1]  # +1: up impulse ending at a high
        y0, y1, y2, y3, y4, y5 = (u * p[2] for p in piv[-6:])
        w1, w3, w5 = y1 - y0, y3 - y2, y5 - y4
        if (y2 > y0 and y3 > y1 and y5 > y3 and y4 > y1 and not (w3 < w1 and w3 < w5)
                and y5 - y0 >= IMPULSE_MIN_ATR * self.atr[piv[-1][0]] and self.once("elliott_impulse", piv, 6)):
            self.P.put("elliott_impulse", i, -u, piv[-1][2])

    def elliott_wave5(self, piv, i: int) -> None:
        u = -piv[-1][1]  # +1: up impulse, P4 is a low
        y0, y1, y2, y3, y4 = (u * p[2] for p in piv[-5:])
        w1, w3 = y1 - y0, y3 - y2
        if (y2 > y0 and y3 > y1 and y4 > y1 and w3 > w1 and _ok((y3 - y4) / w3, WAVE4_RETR)
                and y3 - y0 >= WAVE5_MIN_ATR * self.atr[piv[-1][0]] and self.once("elliott_wave5", piv, 5)):
            self.P.put("elliott_wave5", i, u, piv[-4][2])


def detect(ctx: ChunkCtx) -> Hits:
    D = _Det(ctx)
    with np.errstate(invalid="ignore", divide="ignore"):
        for piv, appended in _zigzag(ctx.swings):
            i = piv[-1][3]  # the candle that confirms the last pivot
            if i >= ctx.n:
                continue
            m = len(piv)
            if appended and m >= 3:
                D.fib(piv, i)
            if m >= 4:
                D.abcd(piv, i)
            if m >= 5:
                D.xabcd(piv, i)
                D.elliott_wave5(piv, i)
            if m >= 6:
                D.three_drives(piv, i)
                D.elliott_impulse(piv, i)
    return D.P.flush(Hits())

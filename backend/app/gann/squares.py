"""Square of Nine (methodology 4.6) and Square of Four (4.7, experimental).

One full turn of the Square of Nine adds exactly 2 to the square root (the odd squares 1, 9, 25, ... lie on one diagonal), so
an anchored level is (sqrt(P0) +- degrees/180)^2. The cross sets are exact integer sets on the spiral; the closed formulas below
are checked against the spiral built cell by cell (tests).
"""
import math

from app.gann.price import round_tick


def sq9_levels(p0: float, tick: float, steps: int = 8, step_deg: float = 45.0) -> list[tuple[float, float]]:
    """(degrees, price) for +-1..steps steps around the anchor price; roots that reach zero or below are skipped."""
    r0 = math.sqrt(p0)
    out = []
    for k in range(-steps, steps + 1):
        if k == 0:
            continue
        deg = k * step_deg
        root = r0 + deg / 180.0
        if root <= 0:
            continue
        out.append((float(deg), round_tick(root * root, tick)))
    return out


def spiral(n_max: int, core: int = 1) -> dict[int, tuple[int, int]]:
    """Number -> (x, y) cell. core=1: Square of Nine (1 at the centre, 2 to its right, counter-clockwise).
    core=4: Square of Four (1..4 fill a 2x2 centre). Built by 'turn left whenever the cell to the left is empty'."""
    if core == 1:
        cells = [(0, 0), (1, 0)]
        dx, dy = 1, 0
    elif core == 4:
        cells = [(0, 0), (1, 0), (1, 1), (0, 1)]
        dx, dy = -1, 0
    else:
        raise ValueError("core must be 1 (Square of Nine) or 4 (Square of Four)")
    pos = {i + 1: c for i, c in enumerate(cells[:n_max])}
    used = set(pos.values())
    x, y = cells[-1]
    n = len(cells)
    while n < n_max:
        lx, ly = -dy, dx  # left turn
        if (x + lx, y + ly) not in used:
            dx, dy = lx, ly
        x, y = x + dx, y + dy
        n += 1
        pos[n] = (x, y)
        used.add((x, y))
    return pos


def cross(kind: str, n_max: int, square: int = 9) -> list[int]:
    """Numbers on the cardinal (horizontal/vertical) or diagonal cross, up to n_max, centre excluded."""
    if square == 4:
        if kind != "diagonal":
            raise ValueError("the Square of Four has no single centre cell, so only its diagonal cross is defined")
        return sorted(n for n, (x, y) in spiral(n_max, core=4).items() if (2 * x - 1) ** 2 == (2 * y - 1) ** 2)
    if square != 9:
        raise ValueError("square must be 9 or 4")
    if kind == "cardinal":
        offs = lambda k: (-3 * k + 1, -k + 1, k + 1, 3 * k + 1)  # noqa: E731
    elif kind == "diagonal":
        offs = lambda k: (-2 * k + 1, 1, 2 * k + 1, 4 * k + 1)  # noqa: E731  (4k^2+4k+1 = (2k+1)^2)
    else:
        raise ValueError("kind must be 'cardinal' or 'diagonal'")
    out, k = [], 1
    while 4 * k * k - 3 * k + 1 <= n_max:
        out += [4 * k * k + o for o in offs(k) if 4 * k * k + o <= n_max]
        k += 1
    return sorted(out)


def cross_levels(numbers: list[int], lo: float, hi: float, norm: float = 1.0) -> list[float]:
    """Cross numbers mapped to prices (number / norm) that fall inside [lo, hi]."""
    return [n / norm for n in numbers if lo <= n / norm <= hi]

"""Astronomical event dates from NASA JPL's public DE421 ephemeris, read with Skyfield (MIT licence).

Positions are geocentric apparent ecliptic longitudes. An event time is found by sampling the longitude difference on a fixed
grid and interpolating the crossing linearly between the two samples around it (well inside the +-2 day event windows).
The ephemeris file (about 17 MB) is downloaded once into data/ephemeris/ (git-ignored).
"""
from datetime import datetime, timezone
from functools import lru_cache

import numpy as np

from app.historical.config import REPO_ROOT

EPH_DIR = REPO_ROOT / "data" / "ephemeris"
BODIES = {"sun": "sun", "moon": "moon", "mercury": "mercury", "mars": "mars barycenter",
          "jupiter": "jupiter barycenter", "saturn": "saturn barycenter"}
DAY = 86400


@lru_cache(maxsize=1)
def load_ephemeris():
    from skyfield.api import Loader

    EPH_DIR.mkdir(parents=True, exist_ok=True)
    load = Loader(str(EPH_DIR), verbose=False)
    return load("de421.bsp"), load.timescale(builtin=True)


def _grid(t0: int, t1: int, step_h: float) -> np.ndarray:
    step = int(step_h * 3600)
    return t0 + step * np.arange(int((t1 - t0) // step) + 2, dtype=np.int64)


def longitudes(body: str, epochs: np.ndarray) -> np.ndarray:
    """Geocentric apparent ecliptic longitude in degrees [0, 360)."""
    from skyfield.framelib import ecliptic_frame

    eph, ts = load_ephemeris()
    t = ts.from_datetimes([datetime.fromtimestamp(int(e), timezone.utc) for e in epochs])
    _, lon, _ = eph["earth"].at(t).observe(eph[BODIES[body]]).apparent().frame_latlon(ecliptic_frame)
    return lon.degrees % 360.0


def _wrap180(x: np.ndarray) -> np.ndarray:
    return (np.asarray(x) + 180.0) % 360.0 - 180.0


def _crossings(epochs: np.ndarray, diff: np.ndarray, target: float) -> list[int]:
    y = _wrap180(diff - target)
    out = []
    for k in range(len(y) - 1):
        a, b = y[k], y[k + 1]
        if (a <= 0 < b or a >= 0 > b) and abs(b - a) < 90:
            out.append(int(epochs[k] + (-a) / (b - a) * (epochs[k + 1] - epochs[k])))
    return out


def moon_phases(t0: int, t1: int) -> list[tuple[int, str]]:
    g = _grid(t0, t1, 3)
    d = longitudes("moon", g) - longitudes("sun", g)
    ev = [(t, "new") for t in _crossings(g, d, 0.0)] + [(t, "full") for t in _crossings(g, d, 180.0)]
    return sorted(e for e in ev if t0 <= e[0] <= t1)


def aspects(body1: str, body2: str, t0: int, t1: int, angles=(0, 90, 180, 270)) -> list[tuple[int, float]]:
    g = _grid(t0, t1, 12)
    d = longitudes(body1, g) - longitudes(body2, g)
    ev = [(t, float(a)) for a in angles for t in _crossings(g, d, float(a))]
    return sorted(e for e in ev if t0 <= e[0] <= t1)


def mercury_stations(t0: int, t1: int) -> list[tuple[int, str]]:
    """Where Mercury's daily geocentric motion changes sign: + to - is the retrograde station, - to + the direct one."""
    g = _grid(t0, t1, 6)
    lon = longitudes("mercury", g)
    motion = _wrap180(np.diff(lon))
    mid = (g[:-1] + g[1:]) // 2
    out = []
    for k in range(len(motion) - 1):
        a, b = motion[k], motion[k + 1]
        if a > 0 >= b or a < 0 <= b:
            t = int(mid[k] + a / (a - b) * (mid[k + 1] - mid[k]))
            if t0 <= t <= t1:
                out.append((t, "retrograde" if a > 0 else "direct"))
    return out


def event_mask(bar_ts: np.ndarray, event_ts, tol_days: int = 2) -> np.ndarray:
    """Candles whose UTC day lies within +- tol_days of an event's UTC day."""
    bday = np.floor_divide(np.asarray(bar_ts, dtype=np.int64), DAY)
    out = np.zeros(len(bday), dtype=bool)
    for e in event_ts:
        d = int(e) // DAY
        out |= np.abs(bday - d) <= tol_days
    return out

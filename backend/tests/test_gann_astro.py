"""Separate, experimental astro events (spec 4.6). Checked against well-known dates, +-1 day."""
import ast
import pathlib
from datetime import datetime, timezone

import numpy as np
import pytest

skyfield = pytest.importorskip("skyfield")

from app.gann.astro.events import (  # noqa: E402
    aspects,
    event_mask,
    mercury_stations,
    moon_phases,
)

DAY = 86400


def ts(*a) -> int:
    return int(datetime(*a, tzinfo=timezone.utc).timestamp())


def near(events, t, kind=None) -> bool:
    return any(abs(e - t) <= DAY and (kind is None or k == kind) for e, k in events)


def test_full_moon_2019_01_21():
    ev = moon_phases(ts(2019, 1, 1), ts(2019, 2, 1))
    assert near(ev, ts(2019, 1, 21, 5, 16), "full") and near(ev, ts(2019, 1, 6, 1, 28), "new")


def test_jupiter_saturn_conjunction_2020_12_21():
    assert near(aspects("jupiter", "saturn", ts(2020, 11, 1), ts(2021, 2, 1), angles=(0,)), ts(2020, 12, 21, 18))


def test_mars_jupiter_conjunction_2018_01_07():
    assert near(aspects("mars", "jupiter", ts(2017, 12, 1), ts(2018, 2, 1), angles=(0,)), ts(2018, 1, 7))


def test_mercury_station_retrograde_2019_03_05():
    ev = mercury_stations(ts(2019, 2, 1), ts(2019, 4, 15))
    assert near(ev, ts(2019, 3, 5, 18), "retrograde") and near(ev, ts(2019, 3, 28, 1), "direct")


def test_event_mask():
    bt = ts(2019, 1, 1) + DAY * np.arange(30, dtype=np.int64)
    m = event_mask(bt, [ts(2019, 1, 15, 12)], tol_days=2)
    assert np.flatnonzero(m).tolist() == [12, 13, 14, 15, 16]


def test_core_does_not_import_astro():
    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "gann"
    for f in root.glob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        names = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        names += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not any("astro" in x for x in names), f"{f.name} imports astro"

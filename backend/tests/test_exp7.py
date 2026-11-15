"""Experiment 7 register, pre-registration and guards (spec sections 4.1, 4.2, 4.7)."""
import pytest

from app.gold_research.exp7 import params as P
from app.gold_research.exp7 import run as R


def test_family_sizes():
    ids = P.test_ids()
    assert {k: len(v) for k, v in ids.items()} == {"timing": 176, "trading": 56, "astro": 16, "descriptive": 12}
    assert len(set(sum(ids.values(), []))) == 260  # every id unique
    assert sum(1 for x in ids["timing"] if x.startswith("T|")) == 152
    assert sum(1 for x in ids["trading"] if x.startswith("F|")) == 20


def test_register_sha_stable():
    a, b = P.register(), P.register()
    assert a["sha"] == b["sha"] and len(a["sha"]) == 64
    assert a["gann_sha"] == P.GannParams().sha()
    assert a["floors"]["filters_kept"] == 300 and a["floors"]["rules_trades"] == 100
    assert a["controls"]["coverage_rule"] == 0.90


def test_develop_refuses_uncommitted_prereg(tmp_path, monkeypatch):
    f = tmp_path / "EXP7_preregistration.json"
    f.write_text("{}")
    monkeypatch.setattr(R, "PREREG", f)
    with pytest.raises(RuntimeError, match="committed"):
        R.develop(log=lambda *_: None)


def test_confirm_runs_once(tmp_path, monkeypatch):
    f = tmp_path / "EXP7_confirmation.json"
    f.write_text("{}")
    monkeypatch.setattr(R, "CONF", f)
    with pytest.raises(RuntimeError, match="once"):
        R.confirm(log=lambda *_: None)


def test_exp7_loader_segments(monkeypatch):
    seen = []
    monkeypatch.setattr(R.store, "load_tf", lambda sym, tf, upto="train", final_test=False: seen.append(upto) or "ok")
    assert R.load("XAUUSD", "H1", "train") == "ok" and R.load("XAUUSD", "H1", "validation") == "ok"
    for bad in ("test", "final", "all"):
        with pytest.raises(ValueError):
            R.load("XAUUSD", "H1", bad)
    assert seen == ["train", "validation"]


def test_prereg_records_prior_trials_2115_and_split_hashes():
    doc = R.prereg_doc()
    assert doc["prior_trials"] == 2115
    assert doc["total_trials"] == 2115 + 260
    assert set(doc["splits"]) == {"XAUUSD", "BTCUSDT"} and all(len(v) == 64 for v in doc["splits"].values())
    assert doc["register_sha"] == P.register()["sha"]

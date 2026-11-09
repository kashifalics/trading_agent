"""Final-test guard rails (no market data)."""
import json

import pytest

from app.gold_research import final_test as F


def test_final_test_refuses_without_a_committed_preregistration(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "SPLIT_DIR", tmp_path)
    with pytest.raises(RuntimeError, match="no pre-registration"):
        F.run_final_test("XAUUSD", log=lambda m: None, i_understand_this_is_once=True)
    (tmp_path / "XAUUSD_preregistration.json").write_text(json.dumps({"sha256": "x"}))
    monkeypatch.setattr(F, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(F, "_committed", lambda p: False)
    with pytest.raises(RuntimeError, match="not committed"):
        F.run_final_test("XAUUSD", log=lambda m: None, i_understand_this_is_once=True)
    monkeypatch.setattr(F, "_committed", lambda p: True)
    with pytest.raises(RuntimeError, match="confirm-final-test"):
        F.run_final_test("XAUUSD", log=lambda m: None)
    with pytest.raises(RuntimeError, match="hash"):
        F.run_final_test("XAUUSD", log=lambda m: None, i_understand_this_is_once=True)


def test_report_says_when_the_test_set_is_no_longer_untouched(monkeypatch):
    monkeypatch.setattr(F, "load_split", lambda s: {"test": {"start": "2023-06-24T00:00:00+00:00"}})
    out = {"symbol": "XAUUSD", "run": "2027-01-01", "run_number": 2, "untouched": False, "preregistration_sha256": "a" * 64,
           "patterns": [], "models": []}
    md = F.render(out, {})
    assert "no longer untouched" in md and "validated set is empty" in md

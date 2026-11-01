"""Regression: QComboBox has no setCurrentData(); calling it crashed Settings on launch."""
from pathlib import Path


def test_no_setcurrentdata_calls():
    root = Path(__file__).resolve().parent.parent
    offenders = [str(p) for p in root.glob("*.py") if "setCurrentData(" in p.read_text(encoding="utf-8", errors="ignore")]
    assert not offenders, offenders

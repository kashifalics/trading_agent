from app.core.events import Event
from app.market_data.bars import Bars
from app.market_structure.bos import detect_structure_breaks
from app.market_structure.swings import Swing


def detect_choch(b: Bars, swings: list[Swing]) -> list[Event]:
    """CHoCH = a structure break against the prevailing trend (see bos.py for the definition)."""
    return [e for e in detect_structure_breaks(b, swings)[0] if e.kind == "CHoCH"]

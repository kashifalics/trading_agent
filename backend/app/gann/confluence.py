"""Gann confluence (methodology 4.12): count independent FAMILIES, never individual levels.

Identities are merged before counting: Square of Four levels are Square of Nine evidence, Square of Twelve twelfths are range
divisions, price-time balance is the 1x1 angle, anniversaries are the 365-day cycle. Twenty Square of Nine levels near a price
count once.
"""
FAMILIES = ("cycles", "seasonal", "divisions", "square9", "angles", "symmetry")
MERGE = {"twelfth": "divisions", "sq4": "square9", "balance": "angles", "anniversary": "cycles"}


def families_at(levels: list[dict], windows: list[dict], price: float, tol: float) -> set[str]:
    """Families with a price level within `tol` of `price`, plus families of the active time windows."""
    out = {lv["family"] for lv in levels if abs(lv["price"] - price) <= tol}
    out |= {w["family"] for w in windows}
    return out

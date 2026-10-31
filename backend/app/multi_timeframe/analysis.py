from dataclasses import dataclass

from app.market_data.bars import Bars
from app.multi_timeframe.alignment import TFView, alignment, build_view, htf_as_of


@dataclass
class MTFConfig:
    higher: str | None = None
    intermediate: str | None = None
    entry: str | None = None

    def roles(self) -> list[tuple[str, str]]:
        return [(r, tf) for r, tf in (("higher", self.higher), ("intermediate", self.intermediate),
                                      ("entry", self.entry)) if tf]


def analyze_mtf(cfg: MTFConfig, bars_by_tf: dict[str, Bars], as_of_epoch: int | None = None) -> dict:
    """as_of_epoch: when given, every timeframe is truncated to candles complete at that instant."""
    views: list[TFView] = []
    for role, tf in cfg.roles():
        b = bars_by_tf.get(tf)
        if b is None:
            continue
        if as_of_epoch is not None:
            b = htf_as_of(b, as_of_epoch)
        views.append(build_view(b, tf, role)[0])
    out = alignment(views)
    out["config"] = {"higher": cfg.higher, "intermediate": cfg.intermediate, "entry": cfg.entry}
    return out

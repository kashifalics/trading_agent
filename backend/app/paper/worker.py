"""In-process paper-trading loop (PAPER_TRADING_INTERVAL_SECONDS > 0). Cycles start a few seconds after each interval boundary, i.e. just
after candles close, so a new signal is seen within seconds. One cycle at a time (service.run_cycle holds a lock); a failing cycle never
stops the loop."""
import asyncio
import logging
import time

from app.core.config import get_settings
from app.paper.service import WORKER, Busy, run_cycle

log = logging.getLogger(__name__)
AFTER_CLOSE_S = 4  # give providers a moment to publish the candle that just closed


def next_delay(interval: int, now: float | None = None) -> float:
    now = time.time() if now is None else now
    return interval - (now % interval) + AFTER_CLOSE_S


async def paper_loop() -> None:
    interval = max(15, get_settings().paper_trading_interval_seconds)
    WORKER.update(enabled=True, interval_s=interval)
    await asyncio.sleep(5)  # let the app finish starting
    while True:
        try:
            res = await asyncio.to_thread(run_cycle)
            WORKER["last_error"] = None
            new = sum(len(r.get("new") or []) for r in res["results"])
            if new:
                log.info("paper trading: %d new signal(s) recorded", new)
        except Busy:
            pass  # a cycle started from the API is still running
        except Exception as exc:  # noqa: BLE001 - the loop must survive any single failure
            log.exception("paper trading cycle crashed")
            WORKER["last_error"] = f"{exc.__class__.__name__}: {exc}"[:200]
        await asyncio.sleep(next_delay(interval))

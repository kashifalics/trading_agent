"""Optional in-process automatic scanning (OPPORTUNITY_SCAN_INTERVAL_MINUTES > 0). With JOB_BACKEND=celery the same
function can be driven by Celery beat instead. Overlapping runs are impossible: create_scan() reuses a live scan."""
import asyncio
import logging
import time

from app.core.config import get_settings
from app.database.session import session_scope
from app.opportunities.scanner import create_scan, execute_scan

log = logging.getLogger(__name__)
RETRIES = 2
BACKOFF_S = 60


def run_scheduled_scan() -> str:
    s = get_settings()
    params = {"refresh_data": True, "refresh_providers": s.opportunity_refresh_list}
    status = "failed"
    for attempt in range(RETRIES + 1):
        with session_scope() as session:
            scan, dup = create_scan(session, None, params, "scheduled")
            if dup:
                return "skipped_already_running"
            execute_scan(session, scan)
            status = scan.status
        if status != "failed":
            break
        log.warning("scheduled scan failed (attempt %d/%d)", attempt + 1, RETRIES + 1)
        time.sleep(BACKOFF_S * (attempt + 1))
    return status


async def scheduler_loop() -> None:
    interval = get_settings().opportunity_scan_interval_minutes * 60
    await asyncio.sleep(30)  # let the app finish starting
    while True:
        try:
            log.info("scheduled scan: %s", await asyncio.to_thread(run_scheduled_scan))
        except Exception:  # noqa: BLE001 - the loop must survive any single failure
            log.exception("scheduled scan crashed")
        await asyncio.sleep(interval)

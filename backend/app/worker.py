"""Single-owner correlation worker with persisted progress and restart-safe transactions."""
import asyncio
import logging
import signal

from sqlalchemy import delete, text

from backend.app.config import get_settings
from backend.app.correlation import process_pending
from backend.app.database import Database
from backend.app.tables import RateBucket
from common.contracts import utcnow

log = logging.getLogger(__name__)


async def correlate_once(db, settings) -> None:
    async with db.sessions() as session, session.begin():
        await process_pending(session, settings)
        minute = int(utcnow().timestamp() // 60)
        await session.execute(delete(RateBucket).where(RateBucket.minute < minute - 60))


async def run() -> None:
    settings = get_settings()
    db = Database(settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    try:
        # Session-level ownership prevents accidentally starting a second state owner.
        async with db.engine.connect() as ownership:
            acquired = await ownership.scalar(text("SELECT pg_try_advisory_lock(78421365)"))
            if not acquired:
                raise RuntimeError("correlation_worker_already_running")
            while not stop.is_set():
                try:
                    # Detect a lost ownership connection before doing more work.
                    await ownership.execute(text("SELECT 1"))
                    await correlate_once(db, settings)
                except Exception:
                    log.exception("correlation_batch_failed")
                    raise  # Supervisor restarts; never silently lose work or ownership.
                try:
                    await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
                except TimeoutError:
                    pass
    finally:
        await db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())

"""Independent explanation worker; inference never blocks correlation or database transactions."""
import asyncio
import logging

from fastapi import HTTPException
from sqlalchemy import select, text

from backend.app.config import get_settings
from backend.app.database import Database
from backend.app.explanations import explain
from backend.app.snapshots import snapshot
from backend.app.tables import Explanation, User
from common.contracts import utcnow

log = logging.getLogger(__name__)


async def process_one(db, settings) -> bool:
    async with db.sessions() as session, session.begin():
        job = (await session.execute(select(Explanation).where(
            Explanation.status == "queued"
        ).order_by(Explanation.created_at).with_for_update(skip_locked=True).limit(1))).scalar_one_or_none()
        if not job:
            return False
        job.status, job.started_at = "running", utcnow()
        job_id, frozen = job.id, job.snapshot
    result = await explain(frozen, settings)
    async with db.sessions() as session, session.begin():
        job = (await session.execute(select(Explanation).where(
            Explanation.id == job_id
        ).with_for_update())).scalar_one()
        user = await session.get(User, job.user_id)
        try:
            current = await snapshot(session, user, job.incident_id) if user and user.active else None
        except HTTPException:
            current = None
        if job.status == "stale" or not current or current["digest"] != job.snapshot_digest:
            job.status, job.result = "stale", None
        else:
            job.result = result
            job.status = "fallback" if result["mode"] == "template" else "complete"
    return True


async def run():
    settings, db = get_settings(), Database(get_settings())
    try:
        async with db.engine.connect() as owner:
            if not await owner.scalar(text("SELECT pg_try_advisory_lock(78421366)")):
                raise RuntimeError("explanation_worker_already_running")
            async with db.sessions() as session, session.begin():
                # Only the owner recovers interrupted jobs; no duplicate model requests on restart.
                jobs = (await session.execute(select(Explanation).where(
                    Explanation.status == "running",
                ))).scalars().all()
                for job in jobs:
                    job.status = "queued"
            while True:
                await owner.execute(text("SELECT 1"))
                if not await process_one(db, settings):
                    await asyncio.sleep(0.5)
    finally:
        await db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())

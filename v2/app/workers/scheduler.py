"""APScheduler — jobs em background dentro do mesmo processo FastAPI."""

import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from ..database import SessionLocal
from ..services.followup import run_followups


scheduler: AsyncIOScheduler | None = None


async def _job_followups():
    db = SessionLocal()
    try:
        result = await run_followups(db)
        logger.info("Follow-up job ran: {}", result)
        # Audit
        from ..models import EventLog
        db.add(EventLog(level="INFO", source="scheduler", actor="system",
                        message=f"Follow-up: {result['triggered']} triggered, {result['sent']} sent, {result['errors']} errors, {result['archived']} archived",
                        payload=str(result)))
        db.commit()
    except Exception as e:
        logger.exception("Follow-up job failed: {}", e)
    finally:
        db.close()


def start_scheduler() -> AsyncIOScheduler:
    global scheduler
    if scheduler is not None:
        return scheduler

    scheduler = AsyncIOScheduler(timezone="Europe/Lisbon")
    # Diariamente às 09:00 Lisboa
    scheduler.add_job(_job_followups, CronTrigger(hour=9, minute=0), id="daily_followups")
    scheduler.start()
    logger.info("Scheduler started — follow-ups daily at 09:00 Lisbon")
    return scheduler


async def run_followups_now() -> dict:
    """Trigger manual via UI."""
    db = SessionLocal()
    try:
        return await run_followups(db)
    finally:
        db.close()


def stop_scheduler() -> None:
    global scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None

"""
APScheduler setup for Module 3's daily plan generation job.
Single-worker model — safe for one Uvicorn process.
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    """
    Start the AsyncIO scheduler and register the 4:00 AM IST daily job.
    Called from FastAPI's lifespan startup.
    """
    global _scheduler
    from app.services.daily_service import generate_all_daily_plans

    _scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    _scheduler.add_job(
        generate_all_daily_plans,
        trigger="cron",
        hour=4,
        minute=0,
        id="daily_plan_generation",
        replace_existing=True,
        misfire_grace_time=3600,    # run up to 1h late if server was briefly down
        coalesce=True,              # run only once if multiple fires were missed
    )
    _scheduler.start()
    logger.info("APScheduler started — daily plan generation scheduled at 04:00 IST")


def stop_scheduler() -> None:
    """Called from FastAPI's lifespan shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down")

"""
APScheduler setup — Modules 3 & 4 scheduled jobs.
Single-worker model — safe for one Uvicorn process.

Registered jobs:
  04:00 IST daily  → generate_all_daily_plans (Module 3)
  06:30 IST daily  → check_missed_days_and_trigger_review (Module 4 risk signal)
  23:00 IST Sunday → generate_all_weekly_reviews (Module 4)
  01:00 IST 1st    → generate_all_monthly_reviews (Module 4)
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    """
    Start the AsyncIO scheduler and register all cron jobs.
    Called from FastAPI's lifespan startup.
    """
    global _scheduler
    from app.services.daily_service import generate_all_daily_plans
    from app.services.analytics_service import (
        generate_all_weekly_reviews,
        generate_all_monthly_reviews,
        check_missed_days_and_trigger_review,
    )

    _scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

    # Module 3 — daily plan generation at 04:00 IST
    _scheduler.add_job(
        generate_all_daily_plans,
        trigger="cron", hour=4, minute=0,
        id="daily_plan_generation",
        replace_existing=True, misfire_grace_time=3600, coalesce=True,
    )

    # Module 4 — missed-days risk check at 06:30 IST
    _scheduler.add_job(
        check_missed_days_and_trigger_review,
        trigger="cron", hour=6, minute=30,
        id="missed_days_risk_check",
        replace_existing=True, misfire_grace_time=1800, coalesce=True,
    )

    # Module 4 — weekly review generation every Sunday at 23:00 IST
    _scheduler.add_job(
        generate_all_weekly_reviews,
        trigger="cron", day_of_week="sun", hour=23, minute=0,
        id="weekly_review_generation",
        replace_existing=True, misfire_grace_time=3600, coalesce=True,
    )

    # Module 4 — monthly review generation on the 1st of every month at 01:00 IST
    _scheduler.add_job(
        generate_all_monthly_reviews,
        trigger="cron", day=1, hour=1, minute=0,
        id="monthly_review_generation",
        replace_existing=True, misfire_grace_time=3600, coalesce=True,
    )

    _scheduler.start()
    logger.info(
        "APScheduler started — "
        "daily@04:00, risk-check@06:30, weekly@Sun23:00, monthly@1st01:00 IST"
    )


def stop_scheduler() -> None:
    """Called from FastAPI's lifespan shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down")

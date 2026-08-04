"""
Analytics service — MongoDB aggregation pipelines for all dashboard/review data.
No AI in this file. All AI calls are in generate_weekly_review / generate_monthly_review.
"""
import asyncio
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app.models.exam import Exam
from app.models.topic import Topic
from app.models.module_start import ModuleStart
from app.models.module_plan import ModulePlan
from app.models.module_plan_day import ModulePlanDay
from app.models.daily_plan import DailyPlan
from app.models.daily_report import DailyReport
from app.models.feedback import Feedback
from app.models.weekly_review import WeeklyReview
from app.models.monthly_review import MonthlyReview
from app.schemas.dashboard import (
    OverallProgressResponse, ActiveModuleSummary,
    PerformanceStats, HoursTimelinePoint, TopicCompletionPoint,
)
from app.services import prediction_service


# ── Dashboard sub-queries ─────────────────────────────────────────────────────

async def get_overall_progress(exam_id: PydanticObjectId) -> OverallProgressResponse:
    exam = await Exam.get(exam_id)
    pipeline = [
        {"$match": {"exam_id": exam_id, "is_leaf": True}},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
            "in_progress": {"$sum": {"$cond": [{"$eq": ["$status", "in_progress"]}, 1, 0]}},
            "not_started": {"$sum": {"$cond": [{"$eq": ["$status", "not_started"]}, 1, 0]}},
        }},
    ]
    result = await Topic.aggregate(pipeline).to_list()
    row = result[0] if result else {"total": 0, "completed": 0, "in_progress": 0, "not_started": 0}
    total = row["total"] or 1
    return OverallProgressResponse(
        completion_pct=round(row["completed"] / total * 100, 1),
        total_leaf_topics=row["total"],
        completed_leaf_topics=row["completed"],
        in_progress_leaf_topics=row["in_progress"],
        not_started_leaf_topics=row["not_started"],
        exam_name=exam.name if exam else "",
        exam_date=exam.exam_date if exam else None,
    )


async def get_active_module_summary(exam_id: PydanticObjectId) -> Optional[ActiveModuleSummary]:
    ms = await ModuleStart.find_one({"exam_id": exam_id, "status": "active"})
    if not ms:
        return None
    topic = await Topic.get(ms.topic_id)
    plan = await ModulePlan.find_one(ModulePlan.module_start_id == ms.id)
    today_plan = await DailyPlan.find_one({
        "module_start_id": ms.id,
        "plan_date": date.today(),
    })
    return ActiveModuleSummary(
        module_name=ms.module_name or "",
        topic_name=topic.name if topic else "",
        day_number=today_plan.module_plan_day_id and 1,  # simplified — exact day_number via plan
        total_days=plan.total_days if plan else 0,
        module_completion_pct=topic.completion_pct if topic else 0.0,
        status=ms.status,
    )


async def get_performance_stats(exam_id: PydanticObjectId) -> PerformanceStats:
    streak, longest, consistency, avg_conf, avg_daily, total_hours = await asyncio.gather(
        prediction_service.compute_current_streak(exam_id),
        prediction_service.compute_longest_streak(exam_id),
        prediction_service.compute_consistency_score(exam_id),
        prediction_service.compute_avg_confidence(exam_id),
        prediction_service.project_completion(exam_id),  # reuse for avg_daily
        _compute_total_hours_studied(exam_id),
    )
    return PerformanceStats(
        current_streak_days=streak,
        longest_streak_days=longest,
        consistency_score=consistency,
        avg_daily_hours_14d=avg_daily.avg_daily_hours_14d,
        total_hours_studied=total_hours,
        avg_confidence=avg_conf,
    )


async def _compute_total_hours_studied(exam_id: PydanticObjectId) -> float:
    ms_ids = [ms.id for ms in await ModuleStart.find({"exam_id": exam_id}).to_list()]
    if not ms_ids:
        return 0.0
    pipeline = [
        {"$match": {"module_start_id": {"$in": ms_ids}, "actual_hours": {"$ne": None}}},
        {"$group": {"_id": None, "total": {"$sum": "$actual_hours"}}},
    ]
    result = await DailyReport.aggregate(pipeline).to_list()
    return round(result[0]["total"] if result else 0.0, 1)


async def get_recent_feedback(exam_id: PydanticObjectId, limit: int = 3) -> list[dict]:
    feedbacks = await Feedback.find({"exam_id": exam_id}).sort("-created_at").limit(limit).to_list()
    return [
        {
            "id": str(fb.id),
            "performance_summary": fb.performance_summary,
            "pace_status": fb.pace_status,
            "risk_level": fb.risk_level,
            "created_at": fb.created_at.isoformat() if fb.created_at else None,
        }
        for fb in feedbacks
    ]


# ── Hours timeline ────────────────────────────────────────────────────────────

async def get_hours_timeline(
    exam_id: PydanticObjectId,
    days: int = 30,
) -> list[HoursTimelinePoint]:
    ms_ids = [ms.id for ms in await ModuleStart.find({"exam_id": exam_id}).to_list()]
    if not ms_ids:
        return []

    cutoff = date.today() - timedelta(days=days)

    # Planned hours: from DailyPlan
    plan_pipeline = [
        {"$match": {"module_start_id": {"$in": ms_ids}, "plan_date": {"$gte": str(cutoff)}}},
        {"$group": {"_id": "$plan_date", "planned": {"$sum": "$planned_hours"}}},
    ]
    # Actual hours: from DailyReport
    actual_pipeline = [
        {"$match": {"module_start_id": {"$in": ms_ids}, "plan_date": {"$gte": str(cutoff)}}},
        {"$group": {"_id": "$plan_date", "actual": {"$sum": "$actual_hours"}}},
    ]

    plan_result, actual_result = await asyncio.gather(
        DailyPlan.aggregate(plan_pipeline).to_list(),
        DailyReport.aggregate(actual_pipeline).to_list(),
    )

    planned_map = {r["_id"]: r["planned"] for r in plan_result}
    actual_map = {r["_id"]: r.get("actual") or 0.0 for r in actual_result}

    all_dates = sorted(set(list(planned_map.keys()) + list(actual_map.keys())))
    points = []
    for d in all_dates:
        planned = planned_map.get(d, 0.0)
        actual = actual_map.get(d, 0.0)
        points.append(HoursTimelinePoint(
            date=str(d),
            planned=round(planned, 1),
            actual=round(actual, 1),
            delta=round(actual - planned, 1),
        ))
    return points


# ── Topic completion breakdown ────────────────────────────────────────────────

async def get_topic_completion_breakdown(exam_id: PydanticObjectId) -> list[TopicCompletionPoint]:
    """Root-level topics with completion %, for the BarChart."""
    root_topics = await Topic.find({"exam_id": exam_id, "parent_id": None}).sort("order_index").to_list()
    return [
        TopicCompletionPoint(
            topic_name=t.name,
            completion_pct=t.completion_pct,
            estimated_hours=t.estimated_hours or 0.0,
            status=t.status,
        )
        for t in root_topics
    ]


# ── Weekly stats computation ──────────────────────────────────────────────────

async def _compute_weekly_stats(
    exam_id: PydanticObjectId,
    week_start: date,
    week_end: date,
) -> dict:
    ms_ids = [ms.id for ms in await ModuleStart.find({"exam_id": exam_id}).to_list()]
    if not ms_ids:
        return _empty_stats()

    week_start_str = str(week_start)
    week_end_str = str(week_end)

    # All daily plans in window
    plans_in_window = await DailyPlan.find({
        "module_start_id": {"$in": ms_ids},
        "plan_date": {"$gte": week_start_str, "$lte": week_end_str},
    }).to_list()
    plan_ids = [p.id for p in plans_in_window]

    # Planned hours
    planned = sum(p.planned_hours for p in plans_in_window)

    # Actual hours
    actual_pipeline = [
        {"$match": {"daily_plan_id": {"$in": plan_ids}}},
        {"$group": {"_id": None, "total": {"$sum": "$actual_hours"}}},
    ]
    actual_result = await DailyReport.aggregate(actual_pipeline).to_list()
    actual = actual_result[0]["total"] if actual_result else 0.0

    # Topics completed this week
    week_start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc)
    week_end_dt = datetime.combine(week_end, datetime.max.time()).replace(tzinfo=timezone.utc)
    topics_completed = await Topic.find({
        "exam_id": exam_id,
        "is_leaf": True,
        "status": "completed",
        "updated_at": {"$gte": week_start_dt, "$lte": week_end_dt},
    }).count()

    active_days = len({p.plan_date for p in plans_in_window if p.status in ("completed", "partially_completed")})
    skipped = 7 - active_days
    avg_prod = round(actual / planned * 100, 1) if planned else None
    consistency = round(active_days / 7 * 100, 1)

    projection = await prediction_service.project_completion(exam_id)
    overall_pct = await _get_exam_completion_pct(exam_id)

    # Per-topic breakdown for Agent 8
    topic_breakdown = await get_topic_completion_breakdown(exam_id)

    return {
        "planned_hours": round(planned, 1),
        "actual_hours": round(actual or 0.0, 1),
        "topics_completed": topics_completed,
        "skipped_days": max(0, skipped),
        "active_days": active_days,
        "avg_productivity_pct": avg_prod,
        "consistency_pct": consistency,
        "exam_completion_pct": overall_pct,
        "days_remaining_exam": projection.days_remaining,
        "projected_finish_date": projection.projected_finish_date,
        "required_daily_hours": projection.required_daily_hours,
        "on_track": projection.on_track,
        "topic_breakdown": [t.model_dump() for t in topic_breakdown],
    }


async def _compute_monthly_stats(exam_id: PydanticObjectId, year: int, month: int) -> dict:
    days_in_month = monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)
    stats = await _compute_weekly_stats(exam_id, month_start, month_end)
    stats["skipped_days"] = max(0, days_in_month - stats["active_days"])
    return stats


async def _get_exam_completion_pct(exam_id: PydanticObjectId) -> float:
    pipeline = [
        {"$match": {"exam_id": exam_id, "is_leaf": True}},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
        }},
    ]
    result = await Topic.aggregate(pipeline).to_list()
    if not result or not result[0]["total"]:
        return 0.0
    return round(result[0]["completed"] / result[0]["total"] * 100, 2)


def _empty_stats() -> dict:
    return {
        "planned_hours": 0.0, "actual_hours": 0.0, "topics_completed": 0,
        "skipped_days": 0, "active_days": 0, "avg_productivity_pct": None,
        "consistency_pct": None, "exam_completion_pct": 0.0,
        "days_remaining_exam": None, "projected_finish_date": None,
        "required_daily_hours": None, "on_track": None, "topic_breakdown": [],
    }


# ── Weekly/Monthly review generation (orchestrates Agent 8) ──────────────────

async def generate_weekly_review(
    exam_id: PydanticObjectId,
    week_start: date,
    trigger_reason: str = "scheduled",
) -> WeeklyReview:
    """Generate and persist a weekly review. Returns existing if already exists."""
    existing = await WeeklyReview.find_one({
        "exam_id": exam_id,
        "week_start_date": week_start,
    })
    if existing:
        return existing

    week_end = week_start + timedelta(days=6)
    stats = await _compute_weekly_stats(exam_id, week_start, week_end)
    exam = await Exam.get(exam_id)

    from app.services.ai import analytics_agent
    ai_response = await analytics_agent.generate_review(
        exam_name=exam.name if exam else "",
        period_type="weekly",
        period_start=week_start,
        period_end=week_end,
        stats=stats,
    )

    review = WeeklyReview(
        exam_id=exam_id,
        week_start_date=week_start,
        week_end_date=week_end,
        planned_hours=stats["planned_hours"],
        actual_hours=stats["actual_hours"],
        topics_completed=stats["topics_completed"],
        skipped_days=stats["skipped_days"],
        active_days=stats["active_days"],
        avg_productivity_pct=stats["avg_productivity_pct"],
        consistency_pct=stats["consistency_pct"],
        strong_topics=[t.model_dump() for t in ai_response.strong_topics],
        weak_topics=[t.model_dump() for t in ai_response.weak_topics],
        ai_summary=ai_response.narrative_summary,
        key_recommendation=ai_response.key_recommendation,
        ai_tone=ai_response.tone,
        ai_raw_response=ai_response.model_dump(),
        exam_completion_pct=stats["exam_completion_pct"],
        days_remaining_exam=stats["days_remaining_exam"],
        projected_finish_date=stats["projected_finish_date"],
        trigger_reason=trigger_reason,
    )
    try:
        await review.insert()
    except DuplicateKeyError:
        return await WeeklyReview.find_one({"exam_id": exam_id, "week_start_date": week_start})
    return review


async def generate_monthly_review(
    exam_id: PydanticObjectId,
    year: int,
    month: int,
) -> MonthlyReview:
    existing = await MonthlyReview.find_one({
        "exam_id": exam_id, "year": year, "month": month,
    })
    if existing:
        return existing

    days_in_month = monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)
    stats = await _compute_monthly_stats(exam_id, year, month)
    exam = await Exam.get(exam_id)

    from app.services.ai import analytics_agent
    ai_response = await analytics_agent.generate_review(
        exam_name=exam.name if exam else "",
        period_type="monthly",
        period_start=month_start,
        period_end=month_end,
        stats=stats,
    )

    review = MonthlyReview(
        exam_id=exam_id,
        month=month, year=year,
        month_start_date=month_start,
        month_end_date=month_end,
        planned_hours=stats["planned_hours"],
        actual_hours=stats["actual_hours"],
        topics_completed=stats["topics_completed"],
        skipped_days=stats["skipped_days"],
        active_days=stats["active_days"],
        avg_productivity_pct=stats["avg_productivity_pct"],
        consistency_pct=stats["consistency_pct"],
        strong_topics=[t.model_dump() for t in ai_response.strong_topics],
        weak_topics=[t.model_dump() for t in ai_response.weak_topics],
        ai_summary=ai_response.narrative_summary,
        key_recommendation=ai_response.key_recommendation,
        ai_tone=ai_response.tone,
        ai_raw_response=ai_response.model_dump(),
        exam_completion_pct=stats["exam_completion_pct"],
        days_remaining_exam=stats["days_remaining_exam"],
        projected_finish_date=stats["projected_finish_date"],
        required_daily_hours=stats["required_daily_hours"],
        on_track=stats["on_track"],
    )
    try:
        await review.insert()
    except DuplicateKeyError:
        return await MonthlyReview.find_one({"exam_id": exam_id, "year": year, "month": month})
    return review


# ── Batch generation (called by scheduler) ───────────────────────────────────

async def generate_all_weekly_reviews(trigger: str = "scheduled") -> None:
    """Called Sunday 23:00 IST by APScheduler."""
    import logging
    logger = logging.getLogger(__name__)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday of current week

    active_exams = await _get_active_exam_ids()
    sem = asyncio.Semaphore(5)

    async def _one(eid):
        async with sem:
            try:
                await generate_weekly_review(eid, week_start, trigger)
            except Exception as e:
                logger.error(f"Weekly review failed for exam {eid}: {e}")

    await asyncio.gather(*[_one(eid) for eid in active_exams])


async def generate_all_monthly_reviews() -> None:
    """Called 1st of month 01:00 IST by APScheduler."""
    import logging
    logger = logging.getLogger(__name__)
    today = date.today()
    # Generate for the month that just ended
    prev = today.replace(day=1) - timedelta(days=1)

    active_exams = await _get_active_exam_ids()
    sem = asyncio.Semaphore(5)

    async def _one(eid):
        async with sem:
            try:
                await generate_monthly_review(eid, prev.year, prev.month)
            except Exception as e:
                logger.error(f"Monthly review failed for exam {eid}: {e}")

    await asyncio.gather(*[_one(eid) for eid in active_exams])


async def check_missed_days_and_trigger_review() -> None:
    """
    Called daily at 06:30 IST. If 3+ consecutive days are missed,
    triggers an early weekly review as a risk signal.
    """
    import logging
    logger = logging.getLogger(__name__)
    active_exams = await _get_active_exam_ids()

    for eid in active_exams:
        streak = await prediction_service.compute_current_streak(eid)
        if streak == 0:  # no activity today or yesterday
            # Check for 3+ consecutive missed days
            missed_count = await _count_consecutive_missed_days(eid)
            if missed_count >= 3:
                today = date.today()
                week_start = today - timedelta(days=today.weekday())
                try:
                    await generate_weekly_review(eid, week_start, trigger_reason="missed_days_risk")
                    logger.info(f"Risk review triggered for exam {eid} — {missed_count} days missed")
                except Exception as e:
                    logger.error(f"Risk review failed for exam {eid}: {e}")


async def _count_consecutive_missed_days(exam_id: PydanticObjectId) -> int:
    """Count consecutive days with no study activity going back from yesterday."""
    ms_ids = [ms.id for ms in await ModuleStart.find({"exam_id": exam_id}).to_list()]
    missed = 0
    check_date = date.today() - timedelta(days=1)
    for _ in range(7):  # check up to 7 days back
        exists = await DailyPlan.find_one({
            "module_start_id": {"$in": ms_ids},
            "plan_date": str(check_date),
            "status": {"$in": ["completed", "partially_completed"]},
        })
        if exists:
            break
        missed += 1
        check_date -= timedelta(days=1)
    return missed


async def _get_active_exam_ids() -> list[PydanticObjectId]:
    active_ms = await ModuleStart.find({"status": "active"}).to_list()
    return list({ms.exam_id for ms in active_ms})

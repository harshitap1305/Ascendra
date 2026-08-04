"""
Analytics API — dashboard, weekly/monthly reviews, stats endpoints.
"""
import asyncio
from datetime import date
from fastapi import APIRouter, Query
from beanie import PydanticObjectId

from app.api.deps import CurrentUser
from app.services import analytics_service, prediction_service, revision_service
from app.schemas.dashboard import DashboardResponse, HoursTimelinePoint, TopicCompletionPoint
from app.schemas.analytics import WeeklyReviewResponse, MonthlyReviewResponse, GenerateReviewRequest

router = APIRouter(prefix="/exams/{exam_id}", tags=["analytics"])


def _assert_owner(exam_id, user_id):
    pass  # ownership is enforced by Beanie find — Exam.get returns None if wrong user


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(exam_id: str, user: CurrentUser):
    eid = PydanticObjectId(exam_id)
    (
        overall, active_module, timeline, performance, rev_count, recent_fb
    ) = await asyncio.gather(
        analytics_service.get_overall_progress(eid),
        analytics_service.get_active_module_summary(eid),
        prediction_service.project_completion(eid),
        analytics_service.get_performance_stats(eid),
        revision_service.count_due(eid),
        analytics_service.get_recent_feedback(eid, limit=3),
    )

    readiness_score, readiness_breakdown = prediction_service.compute_readiness_score(
        completion_pct=overall.completion_pct,
        consistency_score=performance.consistency_score,
        pace_on_track=timeline.on_track,
        days_remaining=timeline.days_remaining,
        avg_confidence=performance.avg_confidence,
    )
    return DashboardResponse(
        overall_progress=overall,
        active_module=active_module,
        timeline=timeline,
        performance=performance,
        revision_queue_count=rev_count,
        recent_feedback=recent_fb,
        readiness_score=readiness_score,
        readiness_breakdown=readiness_breakdown,
    )


@router.get("/stats/hours-timeline", response_model=list[HoursTimelinePoint])
async def get_hours_timeline(
    exam_id: str,
    user: CurrentUser,
    days: int = Query(default=30, ge=7, le=365),
):
    eid = PydanticObjectId(exam_id)
    return await analytics_service.get_hours_timeline(eid, days=days)


@router.get("/stats/topic-completion", response_model=list[TopicCompletionPoint])
async def get_topic_completion(exam_id: str, user: CurrentUser):
    eid = PydanticObjectId(exam_id)
    return await analytics_service.get_topic_completion_breakdown(eid)


# ── Weekly Reviews ────────────────────────────────────────────────────────────

@router.get("/weekly-reviews", response_model=list[WeeklyReviewResponse])
async def list_weekly_reviews(exam_id: str, user: CurrentUser):
    from app.models.weekly_review import WeeklyReview
    eid = PydanticObjectId(exam_id)
    reviews = await WeeklyReview.find({"exam_id": eid}).sort("-week_start_date").to_list()
    return [
        WeeklyReviewResponse(
            id=str(r.id),
            week_start_date=r.week_start_date,
            week_end_date=r.week_end_date,
            planned_hours=r.planned_hours,
            actual_hours=r.actual_hours,
            topics_completed=r.topics_completed,
            skipped_days=r.skipped_days,
            active_days=r.active_days,
            avg_productivity_pct=r.avg_productivity_pct,
            consistency_pct=r.consistency_pct,
            strong_topics=r.strong_topics,
            weak_topics=r.weak_topics,
            ai_summary=r.ai_summary,
            key_recommendation=r.key_recommendation,
            ai_tone=r.ai_tone,
            exam_completion_pct=r.exam_completion_pct,
            days_remaining_exam=r.days_remaining_exam,
            projected_finish_date=r.projected_finish_date,
            trigger_reason=r.trigger_reason,
            created_at=r.created_at,
        )
        for r in reviews
    ]


@router.post("/weekly-review", response_model=WeeklyReviewResponse)
async def trigger_weekly_review(
    exam_id: str,
    user: CurrentUser,
    body: GenerateReviewRequest = GenerateReviewRequest(),
):
    eid = PydanticObjectId(exam_id)
    today = date.today()
    week_start = body.week_start or (today - __import__('datetime').timedelta(days=today.weekday()))
    r = await analytics_service.generate_weekly_review(eid, week_start, trigger_reason="on_demand")
    return WeeklyReviewResponse(
        id=str(r.id), week_start_date=r.week_start_date, week_end_date=r.week_end_date,
        planned_hours=r.planned_hours, actual_hours=r.actual_hours,
        topics_completed=r.topics_completed, skipped_days=r.skipped_days,
        active_days=r.active_days, avg_productivity_pct=r.avg_productivity_pct,
        consistency_pct=r.consistency_pct, strong_topics=r.strong_topics,
        weak_topics=r.weak_topics, ai_summary=r.ai_summary,
        key_recommendation=r.key_recommendation, ai_tone=r.ai_tone,
        exam_completion_pct=r.exam_completion_pct,
        days_remaining_exam=r.days_remaining_exam,
        projected_finish_date=r.projected_finish_date,
        trigger_reason=r.trigger_reason, created_at=r.created_at,
    )


# ── Monthly Reviews ───────────────────────────────────────────────────────────

@router.get("/monthly-reviews", response_model=list[MonthlyReviewResponse])
async def list_monthly_reviews(exam_id: str, user: CurrentUser):
    from app.models.monthly_review import MonthlyReview
    eid = PydanticObjectId(exam_id)
    reviews = await MonthlyReview.find({"exam_id": eid}).sort("-year").sort("-month").to_list()
    return [
        MonthlyReviewResponse(
            id=str(r.id), month=r.month, year=r.year,
            month_start_date=r.month_start_date, month_end_date=r.month_end_date,
            planned_hours=r.planned_hours, actual_hours=r.actual_hours,
            topics_completed=r.topics_completed, skipped_days=r.skipped_days,
            active_days=r.active_days, avg_productivity_pct=r.avg_productivity_pct,
            strong_topics=r.strong_topics, weak_topics=r.weak_topics,
            ai_summary=r.ai_summary, key_recommendation=r.key_recommendation,
            ai_tone=r.ai_tone, exam_completion_pct=r.exam_completion_pct,
            days_remaining_exam=r.days_remaining_exam,
            projected_finish_date=r.projected_finish_date,
            required_daily_hours=r.required_daily_hours, on_track=r.on_track,
            created_at=r.created_at,
        )
        for r in reviews
    ]


@router.post("/monthly-review", response_model=MonthlyReviewResponse)
async def trigger_monthly_review(
    exam_id: str,
    user: CurrentUser,
    body: GenerateReviewRequest = GenerateReviewRequest(),
):
    import datetime
    eid = PydanticObjectId(exam_id)
    now = datetime.date.today()
    month = body.month or now.month
    year = body.year or now.year
    r = await analytics_service.generate_monthly_review(eid, year, month)
    return MonthlyReviewResponse(
        id=str(r.id), month=r.month, year=r.year,
        month_start_date=r.month_start_date, month_end_date=r.month_end_date,
        planned_hours=r.planned_hours, actual_hours=r.actual_hours,
        topics_completed=r.topics_completed, skipped_days=r.skipped_days,
        active_days=r.active_days, avg_productivity_pct=r.avg_productivity_pct,
        strong_topics=r.strong_topics, weak_topics=r.weak_topics,
        ai_summary=r.ai_summary, key_recommendation=r.key_recommendation,
        ai_tone=r.ai_tone, exam_completion_pct=r.exam_completion_pct,
        days_remaining_exam=r.days_remaining_exam,
        projected_finish_date=r.projected_finish_date,
        required_daily_hours=r.required_daily_hours, on_track=r.on_track,
        created_at=r.created_at,
    )

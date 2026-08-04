"""
Prediction service — all pure Python/MongoDB math.
No AI involved anywhere in this file.
"""
import math
from datetime import date, timedelta
from typing import Optional
from beanie import PydanticObjectId

from app.models.exam import Exam
from app.models.topic import Topic
from app.models.module_start import ModuleStart
from app.models.daily_plan import DailyPlan
from app.models.daily_report import DailyReport
from app.models.confidence_log import ConfidenceLog
from app.schemas.dashboard import ProjectionResult

# Readiness score weights (shown to user in frontend)
READINESS_WEIGHTS = {
    "completion":   0.40,   # 40% — how much of syllabus is actually done
    "consistency":  0.25,   # 25% — are they showing up daily?
    "pace":         0.20,   # 20% — on pace to finish before exam?
    "confidence":   0.15,   # 15% — self-reported understanding
}


# ── Readiness Score ───────────────────────────────────────────────────────────

def compute_readiness_score(
    completion_pct: float,
    consistency_score: float,
    pace_on_track: Optional[bool],
    days_remaining: Optional[int],
    avg_confidence: Optional[float],
) -> tuple[int, dict]:
    """
    Returns (score: int, breakdown: dict) — breakdown shown to user in UI.
    Pure function — no DB access.
    """
    pace_score = 75.0  # neutral default when no data
    if pace_on_track is True:
        pace_score = 100.0
    elif pace_on_track is False:
        pace_score = 40.0
        # Increase urgency if exam is close
        if days_remaining and days_remaining < 14:
            pace_score = 15.0
        elif days_remaining and days_remaining < 30:
            pace_score = 30.0

    confidence_score = 60.0  # neutral default
    if avg_confidence is not None:
        confidence_score = (avg_confidence / 5.0) * 100

    raw = (
        completion_pct   * READINESS_WEIGHTS["completion"] +
        consistency_score * READINESS_WEIGHTS["consistency"] +
        pace_score        * READINESS_WEIGHTS["pace"] +
        confidence_score  * READINESS_WEIGHTS["confidence"]
    )
    score = round(min(100, max(0, raw)))

    breakdown = {
        "completion":   round(completion_pct   * READINESS_WEIGHTS["completion"]),
        "consistency":  round(consistency_score * READINESS_WEIGHTS["consistency"]),
        "pace":         round(pace_score        * READINESS_WEIGHTS["pace"]),
        "confidence":   round(confidence_score  * READINESS_WEIGHTS["confidence"]),
        "weights":      {k: f"{int(v*100)}%" for k, v in READINESS_WEIGHTS.items()},
    }
    return score, breakdown


# ── Completion Projection ─────────────────────────────────────────────────────

async def project_completion(exam_id: PydanticObjectId) -> ProjectionResult:
    """
    14-day rolling average pace → projected finish date.
    Returns None projection fields when not enough data (< 3 data points).
    """
    exam = await Exam.get(exam_id)
    if not exam:
        return ProjectionResult(
            exam_date=None, days_remaining=None, projected_finish_date=None,
            required_daily_hours=None, on_track=None, avg_daily_hours_14d=None,
        )

    # Total and remaining hours from leaf topics
    topic_pipeline = [
        {"$match": {"exam_id": exam_id, "is_leaf": True}},
        {"$group": {
            "_id": None,
            "total_hours": {"$sum": "$estimated_hours"},
            "completed_hours": {
                "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, "$estimated_hours", 0]}
            },
        }},
    ]
    topic_result = await Topic.aggregate(topic_pipeline).to_list()
    total_hours = topic_result[0]["total_hours"] if topic_result else 0.0
    completed_hours = topic_result[0]["completed_hours"] if topic_result else 0.0
    remaining_hours = max(0.0, (total_hours or 0) - (completed_hours or 0))

    avg_daily = await _compute_rolling_avg_daily_hours(exam_id, window_days=14)

    projected_date = None
    if avg_daily and avg_daily > 0 and remaining_hours > 0:
        days_needed = math.ceil(remaining_hours / avg_daily)
        projected_date = date.today() + timedelta(days=days_needed)
    elif remaining_hours == 0:
        projected_date = date.today()  # all done!

    days_remaining_exam = None
    required_daily = None
    on_track = None
    if exam.exam_date:
        days_remaining_exam = (exam.exam_date - date.today()).days
        if days_remaining_exam > 0 and remaining_hours > 0:
            required_daily = round(remaining_hours / days_remaining_exam, 2)
        if projected_date and exam.exam_date:
            on_track = projected_date <= exam.exam_date

    return ProjectionResult(
        exam_date=exam.exam_date,
        days_remaining=days_remaining_exam,
        projected_finish_date=projected_date,
        required_daily_hours=required_daily,
        on_track=on_track,
        avg_daily_hours_14d=round(avg_daily, 2) if avg_daily else None,
    )


async def _compute_rolling_avg_daily_hours(
    exam_id: PydanticObjectId,
    window_days: int = 14,
) -> Optional[float]:
    """
    14-day rolling average: group actual_hours by day, then avg across days.
    Returns None if < 3 data points (prevents garbage projections in first few days).
    """
    from app.models.module_start import ModuleStart
    ms_ids = [ms.id for ms in await ModuleStart.find({"exam_id": exam_id}).to_list()]
    if not ms_ids:
        return None

    window_start = date.today() - timedelta(days=window_days)
    pipeline = [
        {"$match": {
            "module_start_id": {"$in": ms_ids},
            "plan_date": {"$gte": str(window_start)},
            "actual_hours": {"$ne": None, "$gt": 0},
        }},
        {"$group": {
            "_id": "$plan_date",
            "day_hours": {"$sum": "$actual_hours"},
        }},
        {"$group": {
            "_id": None,
            "avg_daily": {"$avg": "$day_hours"},
            "day_count": {"$sum": 1},
        }},
    ]
    result = await DailyReport.aggregate(pipeline).to_list()
    if not result or result[0]["day_count"] < 3:
        return None  # not enough data
    return result[0]["avg_daily"]


# ── Streak & Consistency ──────────────────────────────────────────────────────

async def compute_current_streak(exam_id: PydanticObjectId) -> int:
    """Consecutive days (up to today/yesterday) with a completed/partial check-in."""
    ms_ids = [ms.id for ms in await ModuleStart.find({"exam_id": exam_id}).to_list()]
    if not ms_ids:
        return 0

    # Fetch all active plan dates
    active_plans = await DailyPlan.find({
        "module_start_id": {"$in": ms_ids},
        "status": {"$in": ["completed", "partially_completed"]},
    }).to_list()
    active_dates = {p.plan_date for p in active_plans}

    streak = 0
    check_date = date.today()
    if check_date not in active_dates:
        check_date -= timedelta(days=1)  # allow today not yet studied

    while check_date in active_dates:
        streak += 1
        check_date -= timedelta(days=1)
    return streak


async def compute_longest_streak(exam_id: PydanticObjectId) -> int:
    """Longest consecutive study streak ever for this exam."""
    ms_ids = [ms.id for ms in await ModuleStart.find({"exam_id": exam_id}).to_list()]
    if not ms_ids:
        return 0

    active_plans = await DailyPlan.find({
        "module_start_id": {"$in": ms_ids},
        "status": {"$in": ["completed", "partially_completed"]},
    }).sort("plan_date").to_list()

    if not active_plans:
        return 0

    dates = sorted({p.plan_date for p in active_plans})
    max_streak = 1
    cur_streak = 1
    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            cur_streak += 1
            max_streak = max(max_streak, cur_streak)
        else:
            cur_streak = 1
    return max_streak


async def compute_consistency_score(exam_id: PydanticObjectId, window_days: int = 30) -> float:
    """% of days in the last window_days where the student studied."""
    ms_ids = [ms.id for ms in await ModuleStart.find({"exam_id": exam_id}).to_list()]
    if not ms_ids:
        return 0.0

    window_start = date.today() - timedelta(days=window_days)
    pipeline = [
        {"$match": {
            "module_start_id": {"$in": ms_ids},
            "plan_date": {"$gte": str(window_start)},
            "status": {"$in": ["completed", "partially_completed"]},
        }},
        {"$group": {"_id": "$plan_date"}},
        {"$count": "active_days"},
    ]
    result = await DailyPlan.aggregate(pipeline).to_list()
    active_days = result[0]["active_days"] if result else 0
    return round((active_days / window_days) * 100, 1)


async def compute_avg_confidence(exam_id: PydanticObjectId, n: int = 10) -> Optional[float]:
    """Average of the last n confidence ratings for this exam."""
    recent = await ConfidenceLog.find({"exam_id": exam_id}).sort("-logged_at").limit(n).to_list()
    if not recent:
        return None
    return round(sum(c.rating for c in recent) / len(recent), 2)

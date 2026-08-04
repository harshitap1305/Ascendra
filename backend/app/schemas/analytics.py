from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class WeeklyReviewResponse(BaseModel):
    id: str
    week_start_date: date
    week_end_date: date
    planned_hours: float
    actual_hours: float
    topics_completed: int
    skipped_days: int
    active_days: int
    avg_productivity_pct: Optional[float]
    consistency_pct: Optional[float]
    strong_topics: list[dict]
    weak_topics: list[dict]
    ai_summary: str
    key_recommendation: str
    ai_tone: str
    exam_completion_pct: float
    days_remaining_exam: Optional[int]
    projected_finish_date: Optional[date]
    trigger_reason: str
    created_at: datetime


class MonthlyReviewResponse(BaseModel):
    id: str
    month: int
    year: int
    month_start_date: date
    month_end_date: date
    planned_hours: float
    actual_hours: float
    topics_completed: int
    skipped_days: int
    active_days: int
    avg_productivity_pct: Optional[float]
    strong_topics: list[dict]
    weak_topics: list[dict]
    ai_summary: str
    key_recommendation: str
    ai_tone: str
    exam_completion_pct: float
    days_remaining_exam: Optional[int]
    projected_finish_date: Optional[date]
    required_daily_hours: Optional[float]
    on_track: Optional[bool]
    created_at: datetime


class GenerateReviewRequest(BaseModel):
    week_start: Optional[date] = None  # defaults to current week's Monday
    month: Optional[int] = None        # defaults to current month
    year: Optional[int] = None

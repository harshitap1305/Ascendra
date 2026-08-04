from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class OverallProgressResponse(BaseModel):
    completion_pct: float
    total_leaf_topics: int
    completed_leaf_topics: int
    in_progress_leaf_topics: int
    not_started_leaf_topics: int
    exam_name: str
    exam_date: Optional[date]


class ActiveModuleSummary(BaseModel):
    module_name: str
    topic_name: str
    day_number: Optional[int]
    total_days: int
    module_completion_pct: float
    status: str


class ProjectionResult(BaseModel):
    exam_date: Optional[date]
    days_remaining: Optional[int]
    projected_finish_date: Optional[date]
    required_daily_hours: Optional[float]  # to finish before exam date
    on_track: Optional[bool]
    avg_daily_hours_14d: Optional[float]   # the rolling input


class PerformanceStats(BaseModel):
    current_streak_days: int
    longest_streak_days: int
    consistency_score: float    # % of last 30 days with study activity
    avg_daily_hours_14d: Optional[float]
    total_hours_studied: float
    avg_confidence: Optional[float]   # avg of last 10 confidence logs


class DashboardResponse(BaseModel):
    overall_progress: OverallProgressResponse
    active_module: Optional[ActiveModuleSummary]
    timeline: ProjectionResult
    performance: PerformanceStats
    revision_queue_count: int
    recent_feedback: list[dict]
    readiness_score: int                  # 0-100 composite
    readiness_breakdown: dict             # {completion: x, consistency: x, pace: x, confidence: x}


class HoursTimelinePoint(BaseModel):
    date: str                 # "YYYY-MM-DD"
    planned: float
    actual: float
    delta: float              # actual - planned


class TopicCompletionPoint(BaseModel):
    topic_name: str
    completion_pct: float
    estimated_hours: float
    status: str               # not_started | in_progress | completed

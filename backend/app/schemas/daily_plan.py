from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class CheckinRequest(BaseModel):
    raw_text: str

    def model_post_init(self, __context) -> None:
        self.raw_text = self.raw_text.strip()


class DailyTaskResponse(BaseModel):
    task_ref: str
    description: str
    type: str
    estimated_hours: float
    topic_name: str
    resource_detail: Optional[str]


class DailyPlanResponse(BaseModel):
    id: str
    plan_date: date
    tasks: list[dict]
    carry_over_tasks: list[dict]
    planned_hours: float
    daily_goal: str
    status: str
    has_report: bool = False


class FeedbackResponse(BaseModel):
    id: str
    performance_summary: str
    pace_status: str
    risk_level: str
    suggestions: list[str]
    motivational_note: str
    confidence_display: Optional[int]
    plan_adjusted: bool
    adjustment_summary: Optional[str]
    created_at: datetime


class CheckinResponse(BaseModel):
    feedback: FeedbackResponse
    plan_adjusted: bool
    adjustment_summary: Optional[str] = None


class FeedbackHistoryItem(BaseModel):
    id: str
    plan_date: date
    pace_status: str
    risk_level: str
    performance_summary: str
    suggestions: list[str]
    motivational_note: str
    confidence_display: Optional[int]
    plan_adjusted: bool
    adjustment_summary: Optional[str]
    created_at: datetime

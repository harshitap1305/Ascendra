"""
Pydantic schema for Agent 6 (Progress Analyzer) AI output.
"""
from typing import Optional
from pydantic import BaseModel, field_validator


class TaskResult(BaseModel):
    task_ref: str       # matches a task_ref from DailyPlan.tasks
    status: str         # completed | partial | skipped | not_mentioned
    units_completed: Optional[int] = None   # videos watched, questions solved, pages read

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"completed", "partial", "skipped", "not_mentioned"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class ProgressAnalysisResponse(BaseModel):
    task_results: list[TaskResult]
    actual_hours_spent: Optional[float] = None
    confidence_rating: Optional[int] = None    # 1–5 if mentioned by user
    mood_note: Optional[str] = None
    delay_reason: Optional[str] = None
    overall_completion_today: float            # 0.0–1.0 fraction of planned work done

    @field_validator("confidence_rating")
    @classmethod
    def validate_confidence(cls, v):
        if v is not None and not (1 <= v <= 5):
            raise ValueError("confidence_rating must be 1–5")
        return v

    @field_validator("overall_completion_today")
    @classmethod
    def validate_completion(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

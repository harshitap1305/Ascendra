from datetime import date
from typing import Optional
from pydantic import BaseModel, field_validator
from datetime import datetime


class ExamCreate(BaseModel):
    name: str
    description: Optional[str] = None
    exam_date: Optional[date] = None
    target_finish_date: Optional[date] = None
    daily_study_hours: float = 4.0
    experience_level: str = "beginner"
    goal_score: Optional[str] = None

    @field_validator("experience_level")
    @classmethod
    def validate_experience(cls, v: str) -> str:
        allowed = {"beginner", "intermediate", "revision"}
        if v not in allowed:
            raise ValueError(f"experience_level must be one of {allowed}")
        return v

    @field_validator("daily_study_hours")
    @classmethod
    def validate_hours(cls, v: float) -> float:
        if v <= 0 or v > 24:
            raise ValueError("daily_study_hours must be between 0 and 24")
        return v


class ExamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    exam_date: Optional[date] = None
    target_finish_date: Optional[date] = None
    daily_study_hours: Optional[float] = None
    experience_level: Optional[str] = None
    goal_score: Optional[str] = None
    status: Optional[str] = None


class ExamResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str]
    exam_date: Optional[date]
    target_finish_date: Optional[date]
    daily_study_hours: float
    experience_level: str
    goal_score: Optional[str]
    status: str
    created_at: datetime


class ExamSummaryResponse(BaseModel):
    exam_id: str
    total_leaf_topics: int
    completed_leaf_topics: int
    progress_pct: float

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class ModuleStartRequest(BaseModel):
    topic_id: str
    raw_input: str
    daily_hours_available: float
    expected_hours: Optional[float] = None

    @field_validator("daily_hours_available")
    @classmethod
    def validate_hours(cls, v: float) -> float:
        if v <= 0 or v > 20:
            raise ValueError("daily_hours_available must be between 0 and 20")
        return v

    @field_validator("raw_input")
    @classmethod
    def validate_raw_input(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("raw_input is too short — describe your resources and plan")
        return v.strip()


class ModuleStartStatusResponse(BaseModel):
    id: str
    status: str
    error_detail: Optional[str] = None


class ModuleStartResponse(BaseModel):
    id: str
    exam_id: str
    topic_id: str
    raw_input: str
    daily_hours_available: float
    expected_hours: Optional[float]
    status: str
    started_at: datetime

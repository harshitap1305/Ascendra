"""
Pydantic schema for Agent 4 (Planner) AI output.
This is the validated contract between the AI's JSON and the database write.
"""
from typing import Optional
from pydantic import BaseModel, field_validator


class PlanDay(BaseModel):
    day_number: int
    focus_topics: list[str]
    planned_hours: float
    resources_to_cover: list[dict] = []   # [{"type": "video", "detail": "Gate Smashers Ep 1-3"}]
    goals: str                             # one-sentence goal for the day

    @field_validator("planned_hours")
    @classmethod
    def hours_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("planned_hours must be > 0")
        return round(v, 1)


class MasterPlanResponse(BaseModel):
    total_days: int
    summary: str
    days: list[PlanDay]

    @field_validator("days")
    @classmethod
    def days_must_not_be_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("days list cannot be empty")
        return v

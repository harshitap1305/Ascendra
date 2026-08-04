"""
Pydantic schema for Agent 5 (Daily Planner) AI output.
"""
from typing import Optional
from pydantic import BaseModel, field_validator


class DailyTask(BaseModel):
    task_ref: str               # unique ID in this day: "t1", "t2", etc.
    description: str            # e.g. "Watch Gate Smashers videos 7-9 (Semaphores)"
    type: str                   # study | practice | revision | carry_over
    estimated_hours: float
    topic_name: str             # maps back to a subtopic name from the master plan
    resource_detail: Optional[str] = None  # e.g. "Gate Smashers Ep 7-9"

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"study", "practice", "revision", "carry_over"}
        if v not in allowed:
            raise ValueError(f"type must be one of {allowed}")
        return v

    @field_validator("estimated_hours")
    @classmethod
    def validate_hours(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("estimated_hours must be > 0")
        return round(v, 1)


class DailyPlanResponse(BaseModel):
    tasks: list[DailyTask]
    planned_hours: float
    daily_goal: str             # one-sentence focus for the day
    carry_over_note: Optional[str] = None  # note about carry-over if any

    @field_validator("tasks")
    @classmethod
    def tasks_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("tasks list cannot be empty")
        return v

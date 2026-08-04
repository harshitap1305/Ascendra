from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel


class ResourceResponse(BaseModel):
    id: str
    type: str
    title: str
    source_name: Optional[str]
    url: Optional[str]
    total_units: Optional[int]
    units_planned: Optional[int]
    units_completed: int


class PlanDayResponse(BaseModel):
    id: str
    day_number: int
    planned_date: date
    focus_topics: list[str]
    planned_hours: float
    planned_resources: list[dict]
    goals: str
    status: str
    actual_hours: Optional[float]
    notes: Optional[str]


class DayUpdateRequest(BaseModel):
    planned_hours: Optional[float] = None
    planned_resources: Optional[list[dict]] = None
    focus_topics: Optional[list[str]] = None
    goals: Optional[str] = None


class ModulePlanResponse(BaseModel):
    id: str
    module_start_id: str
    total_days: int
    summary: str
    is_accepted: bool
    generated_at: datetime
    days: list[PlanDayResponse]


class ModuleDetailResponse(BaseModel):
    module_start: dict
    resources: list[ResourceResponse]
    plan: Optional[ModulePlanResponse] = None

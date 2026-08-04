from datetime import datetime, date, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class ModulePlanDay(Document):
    module_plan_id: PydanticObjectId
    day_number: int                       # 1-indexed
    planned_date: date                    # started_at + (day_number - 1) days
    focus_topics: list[str]              # topic/subtopic names to cover
    planned_hours: float
    planned_resources: list[dict] = []   # [{"type": "video", "detail": "Gate Smashers Ep 1-3"}]
    goals: str = ""                      # one-sentence goal for the day
    status: str = "pending"             # pending | done | skipped | adjusted
    actual_hours: Optional[float] = None # filled by Module 3 after check-in
    notes: Optional[str] = None         # Module 3 free-text progress notes

    class Settings:
        name = "module_plan_days"
        indexes = [
            IndexModel([("module_plan_id", ASCENDING), ("day_number", ASCENDING)]),
        ]

from datetime import date, datetime, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class DailyReport(Document):
    daily_plan_id: PydanticObjectId
    module_start_id: PydanticObjectId       # denormalized for fast module-level queries
    plan_date: date                          # denormalized for streak computation
    raw_text: str                            # user's verbatim check-in text
    completed_tasks: list[dict] = []
    pending_tasks: list[dict] = []
    actual_hours: Optional[float] = None
    confidence_rating: Optional[int] = None  # 1–5, AI-extracted if user mentions it
    mood_note: Optional[str] = None          # e.g. "felt tired", extracted by AI
    delay_reason: Optional[str] = None       # why tasks weren't finished
    submitted_at: datetime = None

    def model_post_init(self, __context) -> None:
        if self.submitted_at is None:
            self.submitted_at = datetime.now(timezone.utc)

    class Settings:
        name = "daily_reports"
        indexes = [
            IndexModel([("module_start_id", ASCENDING), ("plan_date", ASCENDING)]),
            IndexModel([("daily_plan_id", ASCENDING)], unique=True),  # one report per plan
        ]

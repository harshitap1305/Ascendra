from datetime import datetime, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class ModuleStart(Document):
    exam_id: PydanticObjectId
    topic_id: PydanticObjectId
    raw_input: str                        # user's verbatim text dump
    daily_hours_available: float
    expected_hours: Optional[float] = None
    status: str = "planning"             # planning | active | planning_failed | completed | paused
    error_detail: Optional[str] = None
    started_at: datetime = None
    updated_at: datetime = None

    def model_post_init(self, __context) -> None:
        now = datetime.now(timezone.utc)
        if self.started_at is None:
            self.started_at = now
        if self.updated_at is None:
            self.updated_at = now

    class Settings:
        name = "module_starts"
        indexes = [
            IndexModel([("exam_id", ASCENDING), ("status", ASCENDING)]),
            IndexModel([("topic_id", ASCENDING)]),
        ]

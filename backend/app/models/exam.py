from datetime import datetime, date, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING
from pydantic import field_validator


class Exam(Document):
    user_id: PydanticObjectId
    name: str
    description: Optional[str] = None
    exam_date: Optional[date] = None
    target_finish_date: Optional[date] = None
    daily_study_hours: float = 4.0
    experience_level: str = "beginner"   # beginner | intermediate | revision
    goal_score: Optional[str] = None
    status: str = "active"               # active | paused | completed | archived
    created_at: datetime = None
    updated_at: datetime = None

    def model_post_init(self, __context) -> None:
        now = datetime.now(timezone.utc)
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now

    class Settings:
        name = "exams"
        indexes = [
            IndexModel([("user_id", ASCENDING), ("status", ASCENDING)]),
        ]

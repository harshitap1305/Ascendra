from datetime import date, datetime, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class RevisionSchedule(Document):
    topic_id: PydanticObjectId
    exam_id: PydanticObjectId               # denormalized for fast queue queries
    topic_name: str                          # denormalized for display (no extra fetch)
    module_name: str = ""                    # denormalized for context in RevisionCard
    revision_number: int                     # 0=extra, 1=day-1, 2=day-3, 3=day-7, 4=day-15, 5=day-30
    scheduled_date: date
    status: str = "pending"                  # pending | done | skipped
    trigger_reason: str                      # spaced_repetition | low_confidence
    completed_at: Optional[datetime] = None
    completion_confidence: Optional[int] = None  # 1-5 recorded when done
    # Re-revision flag: if user rates ≤2 during revision, we ask them in UI
    re_revision_requested: bool = False
    created_at: datetime = None

    def model_post_init(self, __context) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    class Settings:
        name = "revision_schedule"
        indexes = [
            IndexModel(
                [("exam_id", ASCENDING), ("scheduled_date", ASCENDING), ("status", ASCENDING)],
            ),
            IndexModel([("topic_id", ASCENDING), ("revision_number", ASCENDING)]),
            IndexModel([("exam_id", ASCENDING), ("status", ASCENDING)]),
        ]

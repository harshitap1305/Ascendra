from datetime import datetime, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class ConfidenceLog(Document):
    topic_id: PydanticObjectId
    exam_id: PydanticObjectId          # denormalized for avg queries
    topic_name: str                    # denormalized for display
    rating: int                        # 1-5
    context: str                       # checkin | module_complete | revision_done
    revision_schedule_id: Optional[PydanticObjectId] = None  # if logged during revision
    logged_at: datetime = None

    def model_post_init(self, __context) -> None:
        if self.logged_at is None:
            self.logged_at = datetime.now(timezone.utc)

    class Settings:
        name = "confidence_logs"
        indexes = [
            IndexModel([("exam_id", ASCENDING), ("logged_at", ASCENDING)]),
            IndexModel([("topic_id", ASCENDING)]),
        ]

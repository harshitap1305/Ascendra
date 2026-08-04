from datetime import datetime, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class StudyLog(Document):
    """
    Granular per-topic progress entry. One per topic touched per check-in.
    Provides the audit trail for topic completion updates.
    """
    daily_report_id: PydanticObjectId
    topic_id: PydanticObjectId
    module_start_id: PydanticObjectId       # denormalized for module-level rollup queries
    status_change: str                       # completed | in_progress | partial | skipped
    units_completed: Optional[int] = None   # e.g. 5 videos, 20 questions, 3 pages
    logged_at: datetime = None

    def model_post_init(self, __context) -> None:
        if self.logged_at is None:
            self.logged_at = datetime.now(timezone.utc)

    class Settings:
        name = "study_logs"
        indexes = [
            IndexModel([("module_start_id", ASCENDING), ("logged_at", ASCENDING)]),
            IndexModel([("topic_id", ASCENDING)]),
            IndexModel([("daily_report_id", ASCENDING)]),
        ]

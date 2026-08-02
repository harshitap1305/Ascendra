from datetime import datetime, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class RawSyllabusUpload(Document):
    exam_id: PydanticObjectId
    raw_text: str
    parsed_status: str = "pending"     # pending | success | failed
    ai_model_used: Optional[str] = None
    error_detail: Optional[str] = None
    created_at: datetime = None

    def model_post_init(self, __context) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    class Settings:
        name = "raw_syllabus_uploads"
        indexes = [
            IndexModel([("exam_id", ASCENDING)]),
        ]

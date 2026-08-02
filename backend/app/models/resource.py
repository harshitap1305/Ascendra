from datetime import datetime, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class Resource(Document):
    exam_id: PydanticObjectId
    topic_id: Optional[PydanticObjectId] = None   # null = exam-wide resource
    type: str                    # video | book | website | pyq | notes | other
    title: str
    source_name: Optional[str] = None   # e.g. "Gate Smashers", "Galvin"
    url: Optional[str] = None
    total_units: Optional[int] = None   # total videos, total pages, etc.
    created_at: datetime = None

    def model_post_init(self, __context) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    class Settings:
        name = "resources"
        indexes = [
            IndexModel([("exam_id", ASCENDING)]),
        ]

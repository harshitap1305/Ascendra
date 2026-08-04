from datetime import datetime, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class ModuleResource(Document):
    module_start_id: PydanticObjectId
    exam_id: PydanticObjectId
    topic_id: PydanticObjectId
    type: str                            # video | book | practice | revision | other
    title: str
    source_name: Optional[str] = None   # "Gate Smashers", "Galvin"
    url: Optional[str] = None
    total_units: Optional[int] = None   # total videos / pages / questions
    units_planned: Optional[int] = None
    units_completed: int = 0             # updated by Module 3
    created_at: datetime = None

    def model_post_init(self, __context) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    class Settings:
        name = "module_resources"
        indexes = [
            IndexModel([("module_start_id", ASCENDING)]),
            IndexModel([("exam_id", ASCENDING)]),
        ]

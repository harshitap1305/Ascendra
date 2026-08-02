from datetime import datetime, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class Topic(Document):
    exam_id: PydanticObjectId
    parent_id: Optional[PydanticObjectId] = None
    # All ancestor IDs from root → immediate parent (empty list for root topics)
    ancestors: list[PydanticObjectId] = []
    name: str
    depth: int = 0          # 0 = root topic, 1 = subtopic, 2 = sub-subtopic
    order_index: int = 0    # preserves syllabus order
    is_leaf: bool = True    # True if no children

    # AI-enriched fields (filled by difficulty estimator, Agent 2)
    difficulty: Optional[str] = None        # low | medium | high
    estimated_hours: Optional[float] = None
    weightage: Optional[float] = None       # % of exam marks/questions
    prerequisite_topic_id: Optional[PydanticObjectId] = None

    # Progress (updated by Module 3)
    status: str = "not_started"             # not_started | in_progress | completed | skipped
    completion_pct: float = 0.0

    created_at: datetime = None
    updated_at: datetime = None

    def model_post_init(self, __context) -> None:
        now = datetime.now(timezone.utc)
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now

    class Settings:
        name = "topics"
        indexes = [
            IndexModel([("exam_id", ASCENDING), ("parent_id", ASCENDING)]),
            IndexModel([("exam_id", ASCENDING), ("status", ASCENDING)]),
            IndexModel([("ancestors", ASCENDING)]),   # fast subtree queries
        ]

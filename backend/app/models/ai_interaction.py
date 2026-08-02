from datetime import datetime, timezone
from typing import Any, Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class AIInteraction(Document):
    user_id: PydanticObjectId
    exam_id: Optional[PydanticObjectId] = None
    agent_type: str        # syllabus_parser | difficulty_estimator | planner | ...
    input_payload: dict    # exact context sent to AI
    output_payload: Optional[dict] = None  # raw AI response (None if failed)
    model_used: Optional[str] = None
    latency_ms: Optional[int] = None
    token_count: Optional[int] = None
    status: str = "success"    # success | failed | retried
    created_at: datetime = None

    def model_post_init(self, __context) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    class Settings:
        name = "ai_interactions"
        indexes = [
            IndexModel([("user_id", ASCENDING), ("created_at", ASCENDING)]),
            IndexModel([("exam_id", ASCENDING)]),
        ]

from datetime import datetime, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class Feedback(Document):
    """
    Mentor's response after each check-in.
    Stores the full AI narrative + computed pace metrics.
    """
    daily_report_id: PydanticObjectId
    module_start_id: PydanticObjectId
    exam_id: PydanticObjectId               # denormalized for exam-wide feedback history
    performance_summary: str
    pace_status: str                         # ahead | on_track | behind | at_risk
    risk_level: str                          # low | medium | high
    suggestions: list[str] = []
    motivational_note: str = ""
    confidence_display: Optional[int] = None # 1–5, displayed in FeedbackCard if extracted
    # Replanning outcome (always runs after check-in)
    plan_adjusted: bool = False
    adjustment_summary: Optional[str] = None
    ai_raw_response: dict = {}
    created_at: datetime = None

    def model_post_init(self, __context) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    class Settings:
        name = "feedback"
        indexes = [
            IndexModel([("exam_id", ASCENDING), ("created_at", ASCENDING)]),
            IndexModel([("module_start_id", ASCENDING), ("created_at", ASCENDING)]),
            IndexModel([("daily_report_id", ASCENDING)], unique=True),
        ]

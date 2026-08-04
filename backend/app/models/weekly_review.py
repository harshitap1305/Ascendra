from datetime import date, datetime, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class WeeklyReview(Document):
    exam_id: PydanticObjectId
    week_start_date: date
    week_end_date: date
    # Computed stats (deterministic Python/MongoDB, NOT AI)
    planned_hours: float = 0.0
    actual_hours: float = 0.0
    topics_completed: int = 0
    skipped_days: int = 0
    active_days: int = 0
    avg_productivity_pct: Optional[float] = None   # actual/planned * 100
    consistency_pct: Optional[float] = None         # % of planned days studied
    # AI-generated fields (Agent 8)
    strong_topics: list[dict] = []      # [{name, reason}]
    weak_topics: list[dict] = []        # [{name, reason}]
    ai_summary: str = ""
    key_recommendation: str = ""
    ai_tone: str = "balanced"           # encouraging | urgent | balanced
    ai_raw_response: dict = {}
    # Context snapshot
    exam_completion_pct: float = 0.0    # overall at time of review
    days_remaining_exam: Optional[int] = None
    projected_finish_date: Optional[date] = None
    trigger_reason: str = "scheduled"   # scheduled | on_demand | missed_days_risk
    created_at: datetime = None

    def model_post_init(self, __context) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    class Settings:
        name = "weekly_reviews"
        indexes = [
            IndexModel(
                [("exam_id", ASCENDING), ("week_start_date", ASCENDING)],
                unique=True,
            ),
            IndexModel([("exam_id", ASCENDING), ("created_at", ASCENDING)]),
        ]

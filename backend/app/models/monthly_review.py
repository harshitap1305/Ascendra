from datetime import date, datetime, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class MonthlyReview(Document):
    exam_id: PydanticObjectId
    month: int           # 1-12
    year: int
    month_start_date: date
    month_end_date: date
    # Computed stats
    planned_hours: float = 0.0
    actual_hours: float = 0.0
    topics_completed: int = 0
    skipped_days: int = 0
    active_days: int = 0
    avg_productivity_pct: Optional[float] = None
    consistency_pct: Optional[float] = None
    # Prediction fields (set at review time, deterministic)
    projected_finish_date: Optional[date] = None
    required_daily_hours: Optional[float] = None   # to finish before exam date
    on_track: Optional[bool] = None
    # AI-generated
    strong_topics: list[dict] = []
    weak_topics: list[dict] = []
    ai_summary: str = ""
    key_recommendation: str = ""
    ai_tone: str = "balanced"
    ai_raw_response: dict = {}
    # Context
    exam_completion_pct: float = 0.0
    days_remaining_exam: Optional[int] = None
    created_at: datetime = None

    def model_post_init(self, __context) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    class Settings:
        name = "monthly_reviews"
        indexes = [
            IndexModel(
                [("exam_id", ASCENDING), ("year", ASCENDING), ("month", ASCENDING)],
                unique=True,
            ),
        ]

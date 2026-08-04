from datetime import date, datetime, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class DailyPlan(Document):
    module_start_id: PydanticObjectId
    module_plan_day_id: PydanticObjectId    # links to Module 2 master-plan day
    plan_date: date                          # the calendar date this covers
    tasks: list[dict] = []                   # [{task_ref, description, type, estimated_hours, topic_name, resource_detail}]
    planned_hours: float = 0.0
    daily_goal: str = ""                     # AI-generated one-sentence focus
    carry_over_tasks: list[dict] = []        # tasks brought forward from previous day
    status: str = "pending"                  # pending | completed | partially_completed | skipped
    ai_raw_response: dict = {}
    created_at: datetime = None

    def model_post_init(self, __context) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    class Settings:
        name = "daily_plans"
        indexes = [
            # Unique: one plan per module per day — prevents race-condition duplicates
            IndexModel(
                [("module_start_id", ASCENDING), ("plan_date", ASCENDING)],
                unique=True,
            ),
        ]

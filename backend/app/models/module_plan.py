from datetime import datetime, timezone
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class ModulePlan(Document):
    module_start_id: PydanticObjectId
    total_days: int
    summary: str                          # AI-generated short overview
    ai_raw_response: dict                 # full AI JSON stored verbatim for audit
    generated_at: datetime = None
    is_accepted: bool = False             # user explicitly accepted plan before Module 3 runs

    def model_post_init(self, __context) -> None:
        if self.generated_at is None:
            self.generated_at = datetime.now(timezone.utc)

    class Settings:
        name = "module_plans"
        indexes = [
            IndexModel([("module_start_id", ASCENDING)], unique=True),
        ]

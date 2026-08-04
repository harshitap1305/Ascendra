from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class RevisionItem(BaseModel):
    id: str
    topic_name: str
    module_name: str
    revision_number: int
    revision_label: str    # "Urgent", "Revision 1/5", "Revision 3/5", etc.
    scheduled_date: date
    days_overdue: int      # 0 = due today, >0 = overdue
    trigger_reason: str    # spaced_repetition | low_confidence
    status: str


class RevisionCompleteRequest(BaseModel):
    confidence_rating: Optional[int] = None   # 1-5, optional

    @field_validator("confidence_rating")
    @classmethod
    def validate_rating(cls, v):
        if v is not None and not (1 <= v <= 5):
            raise ValueError("confidence_rating must be 1-5")
        return v


class RevisionCompleteResponse(BaseModel):
    revision_id: str
    status: str
    show_re_revision_prompt: bool    # True if rating ≤ 2 — frontend shows "schedule another?"
    confidence_logged: Optional[int]


class ConfidenceLogRequest(BaseModel):
    rating: int
    context: str = "module_complete"  # checkin | module_complete | revision_done

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v):
        if not (1 <= v <= 5):
            raise ValueError("rating must be 1-5")
        return v

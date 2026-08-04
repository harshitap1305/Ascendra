"""
Pydantic schema for Agent 7 (Feedback Generator) AI output.
"""
from pydantic import BaseModel, field_validator


class FeedbackResponse(BaseModel):
    performance_summary: str        # "You completed 3/4 tasks today, solved 18/30 PYQs"
    pace_status: str                # ahead | on_track | behind | at_risk
    risk_level: str                 # low | medium | high
    suggestions: list[str]          # 2–3 concrete actionable items
    motivational_note: str          # mentor-tone encouragement

    @field_validator("pace_status")
    @classmethod
    def validate_pace_status(cls, v: str) -> str:
        allowed = {"ahead", "on_track", "behind", "at_risk"}
        if v not in allowed:
            raise ValueError(f"pace_status must be one of {allowed}")
        return v

    @field_validator("risk_level")
    @classmethod
    def validate_risk(cls, v: str) -> str:
        if v not in {"low", "medium", "high"}:
            raise ValueError("risk_level must be low|medium|high")
        return v

    @field_validator("suggestions")
    @classmethod
    def suggestions_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("suggestions must have at least one item")
        return v[:5]  # cap at 5 to avoid verbosity

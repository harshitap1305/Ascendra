"""
Agent 8 (Analytics Reviewer) AI output schema.
"""
from typing import Optional
from pydantic import BaseModel, field_validator


class TopicInsight(BaseModel):
    name: str
    reason: str   # 1-sentence explanation

    
class AnalyticsReviewResponse(BaseModel):
    narrative_summary: str           # 2-3 paragraphs
    strong_topics: list[TopicInsight]
    weak_topics: list[TopicInsight]
    key_recommendation: str          # single most important action for next period
    tone: str                        # encouraging | urgent | balanced

    @field_validator("strong_topics", "weak_topics")
    @classmethod
    def cap_at_three(cls, v):
        return v[:3]

    @field_validator("tone")
    @classmethod
    def validate_tone(cls, v):
        if v not in {"encouraging", "urgent", "balanced"}:
            return "balanced"
        return v

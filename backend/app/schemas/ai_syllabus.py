"""
Pydantic schemas that exactly mirror the AI prompt JSON schemas.
These are used to validate AI responses before any DB writes.
"""
from typing import Optional
from pydantic import BaseModel


# ── Agent 1: Syllabus Parser ──────────────────────────────────────────────────

class ParsedTopicNode(BaseModel):
    name: str
    order_index: int
    weightage: Optional[float] = None
    children: list["ParsedTopicNode"] = []


class ParsedSyllabusResponse(BaseModel):
    topics: list[ParsedTopicNode]


# ── Agent 2: Difficulty Estimator ────────────────────────────────────────────

class EnrichedTopicNode(BaseModel):
    id: str
    difficulty: str                         # low | medium | high
    estimated_hours: float
    weightage: Optional[float] = None
    prerequisite_topic_name: Optional[str] = None
    children: list["EnrichedTopicNode"] = []


class EnrichedTopicsResponse(BaseModel):
    topics: list[EnrichedTopicNode]

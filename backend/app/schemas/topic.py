from typing import Optional, Any
from pydantic import BaseModel


class TopicResponse(BaseModel):
    id: str
    exam_id: str
    parent_id: Optional[str]
    name: str
    depth: int
    order_index: int
    is_leaf: bool
    difficulty: Optional[str]
    estimated_hours: Optional[float]
    weightage: Optional[float]
    prerequisite_topic_id: Optional[str]
    status: str
    completion_pct: float
    children: list["TopicResponse"] = []


class TopicUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None   # reparent — triggers ancestors rebuild
    order_index: Optional[int] = None
    status: Optional[str] = None


class SyllabusUploadRequest(BaseModel):
    raw_text: str


class SyllabusUploadResponse(BaseModel):
    upload_id: str
    parsed_status: str


class EnrichStatusResponse(BaseModel):
    exam_id: str
    enriched_count: int
    failed_count: int

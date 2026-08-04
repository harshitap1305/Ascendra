"""
Confidence logging endpoint.
POST /topics/{topic_id}/confidence — log a confidence rating for a topic.
Triggered from module completion, check-in, or revision.
"""
from fastapi import APIRouter
from beanie import PydanticObjectId

from app.api.deps import CurrentUser
from app.services.revision_service import maybe_schedule_confidence_revision
from app.schemas.revision import ConfidenceLogRequest

router = APIRouter(tags=["confidence"])


@router.post("/topics/{topic_id}/confidence")
async def log_confidence(
    topic_id: str,
    body: ConfidenceLogRequest,
    user: CurrentUser,
):
    """
    Log a confidence rating for a topic.
    If context='checkin' and rating ≤ 2, also schedules an urgent extra revision.
    """
    tid = PydanticObjectId(topic_id)
    await maybe_schedule_confidence_revision(
        topic_id=tid,
        rating=body.rating,
        context=body.context,
    )
    return {"status": "logged", "rating": body.rating, "context": body.context}

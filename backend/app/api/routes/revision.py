"""
Revision queue API — get queue, mark done/skip, request re-revision.
"""
from fastapi import APIRouter
from beanie import PydanticObjectId

from app.api.deps import CurrentUser
from app.services import revision_service
from app.schemas.revision import RevisionCompleteRequest, RevisionCompleteResponse, RevisionItem

router = APIRouter(tags=["revision"])


@router.get("/exams/{exam_id}/revision-queue", response_model=list[RevisionItem])
async def get_revision_queue(exam_id: str, user: CurrentUser):
    eid = PydanticObjectId(exam_id)
    items = await revision_service.get_revision_queue(eid)
    return [RevisionItem(**item) for item in items]


@router.get("/exams/{exam_id}/revision-queue/upcoming")
async def get_upcoming_revisions(exam_id: str, user: CurrentUser):
    eid = PydanticObjectId(exam_id)
    return await revision_service.get_upcoming_revisions(eid, days_ahead=7)


@router.post("/revisions/{revision_id}/complete", response_model=RevisionCompleteResponse)
async def complete_revision(
    revision_id: str,
    body: RevisionCompleteRequest,
    user: CurrentUser,
):
    rid = PydanticObjectId(revision_id)
    result = await revision_service.complete_revision(rid, body.confidence_rating)
    return RevisionCompleteResponse(**result)


@router.post("/revisions/{revision_id}/re-revision")
async def request_re_revision(revision_id: str, user: CurrentUser):
    """Called when user confirms 'Yes, schedule another revision' after rating ≤ 2."""
    rid = PydanticObjectId(revision_id)
    extra = await revision_service.request_re_revision(rid)
    return {"id": str(extra.id), "scheduled_date": str(extra.scheduled_date), "status": "scheduled"}


@router.post("/revisions/{revision_id}/skip")
async def skip_revision(revision_id: str, user: CurrentUser):
    """Reschedule a revision to tomorrow."""
    rid = PydanticObjectId(revision_id)
    r = await revision_service.skip_revision(rid)
    return {"id": str(r.id), "new_scheduled_date": str(r.scheduled_date)}

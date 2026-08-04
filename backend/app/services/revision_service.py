"""
Revision service — spaced repetition scheduling.
Fixed intervals 1/3/7/15/30 days.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from beanie import PydanticObjectId

from app.models.topic import Topic
from app.models.revision_schedule import RevisionSchedule
from app.models.confidence_log import ConfidenceLog

REVISION_INTERVALS_DAYS = [1, 3, 7, 15, 30]
REVISION_LABELS = {1: "day-1", 2: "day-3", 3: "day-7", 4: "day-15", 5: "day-30"}


async def schedule_revisions_for_topic(topic: Topic) -> None:
    """
    Called when a leaf topic transitions to status='completed'.
    Creates 5 revision schedule entries at fixed intervals.
    """
    # Don't duplicate if revisions already exist for this topic
    existing_count = await RevisionSchedule.find({
        "topic_id": topic.id,
        "trigger_reason": "spaced_repetition",
    }).count()
    if existing_count > 0:
        return  # already scheduled (e.g. topic was completed → reset → completed again)

    completion_date = date.today()
    docs = [
        RevisionSchedule(
            topic_id=topic.id,
            exam_id=topic.exam_id,
            topic_name=topic.name,
            revision_number=i,
            scheduled_date=completion_date + timedelta(days=interval),
            trigger_reason="spaced_repetition",
        )
        for i, interval in enumerate(REVISION_INTERVALS_DAYS, start=1)
    ]
    await RevisionSchedule.insert_many(docs)


async def maybe_schedule_confidence_revision(
    topic_id: PydanticObjectId,
    rating: Optional[int],
    context: str = "checkin",
    revision_schedule_id: Optional[PydanticObjectId] = None,
) -> None:
    """
    Log a confidence rating and flag re-revision if rating ≤ 2.
    For revision completions, we don't auto-schedule — instead we set
    re_revision_requested=True so the frontend can ask the user.
    For initial check-ins (context='checkin') with rating ≤ 2, we auto-schedule
    an urgent extra revision since the user is still learning the topic.
    """
    if not rating or not (1 <= rating <= 5):
        return

    topic = await Topic.get(topic_id)
    if not topic:
        return

    # Log the confidence rating
    await ConfidenceLog(
        topic_id=topic_id,
        exam_id=topic.exam_id,
        topic_name=topic.name,
        rating=rating,
        context=context,
        revision_schedule_id=revision_schedule_id,
    ).insert()

    if context == "checkin" and rating <= 2:
        # Auto-schedule an urgent extra revision (revision_number=0)
        await RevisionSchedule(
            topic_id=topic_id,
            exam_id=topic.exam_id,
            topic_name=topic.name,
            revision_number=0,
            scheduled_date=date.today() + timedelta(days=1),
            trigger_reason="low_confidence",
        ).insert()


async def complete_revision(
    revision_id: PydanticObjectId,
    confidence_rating: Optional[int] = None,
) -> dict:
    """
    Mark a revision done. Returns show_re_revision_prompt=True if rating ≤ 2.
    Does NOT auto-schedule another revision — that's a user choice (shown in frontend).
    """
    revision = await RevisionSchedule.get(revision_id)
    if not revision:
        raise ValueError("Revision not found")

    revision.status = "done"
    revision.completed_at = datetime.now(timezone.utc)
    revision.completion_confidence = confidence_rating
    if confidence_rating and confidence_rating <= 2:
        revision.re_revision_requested = True
    await revision.save()

    # Log confidence if provided
    if confidence_rating:
        await maybe_schedule_confidence_revision(
            topic_id=revision.topic_id,
            rating=confidence_rating,
            context="revision_done",
            revision_schedule_id=revision.id,
        )

    show_prompt = bool(confidence_rating and confidence_rating <= 2)
    return {
        "revision_id": str(revision.id),
        "status": "done",
        "show_re_revision_prompt": show_prompt,
        "confidence_logged": confidence_rating,
    }


async def request_re_revision(revision_id: PydanticObjectId) -> RevisionSchedule:
    """
    Called when user clicks 'Yes, schedule another' after seeing the prompt.
    Creates an extra revision scheduled for tomorrow.
    """
    original = await RevisionSchedule.get(revision_id)
    if not original:
        raise ValueError("Original revision not found")

    extra = RevisionSchedule(
        topic_id=original.topic_id,
        exam_id=original.exam_id,
        topic_name=original.topic_name,
        revision_number=0,  # extra
        scheduled_date=date.today() + timedelta(days=1),
        trigger_reason="low_confidence",
    )
    await extra.insert()
    return extra


async def skip_revision(revision_id: PydanticObjectId) -> RevisionSchedule:
    """Reschedule a revision to tomorrow (soft skip)."""
    revision = await RevisionSchedule.get(revision_id)
    if not revision:
        raise ValueError("Revision not found")
    revision.scheduled_date = date.today() + timedelta(days=1)
    revision.status = "pending"
    await revision.save()
    return revision


async def count_due(exam_id: PydanticObjectId) -> int:
    """Count revisions due today or overdue for badge display."""
    return await RevisionSchedule.find({
        "exam_id": exam_id,
        "status": "pending",
        "scheduled_date": {"$lte": str(date.today())},
    }).count()


async def get_revision_queue(exam_id: PydanticObjectId) -> list[dict]:
    """
    Today's + overdue pending revisions, ordered by scheduled_date.
    Returns enriched dicts with display-ready label and days_overdue.
    """
    revisions = await RevisionSchedule.find({
        "exam_id": exam_id,
        "status": "pending",
        "scheduled_date": {"$lte": str(date.today())},
    }).sort("scheduled_date").to_list()

    today = date.today()
    result = []
    for r in revisions:
        if r.revision_number == 0:
            label = "Urgent Revision"
        else:
            label = f"Revision {r.revision_number}/5 ({REVISION_LABELS.get(r.revision_number, '')})"

        days_overdue = max(0, (today - r.scheduled_date).days)
        result.append({
            "id": str(r.id),
            "topic_name": r.topic_name,
            "module_name": r.module_name,
            "revision_number": r.revision_number,
            "revision_label": label,
            "scheduled_date": str(r.scheduled_date),
            "days_overdue": days_overdue,
            "trigger_reason": r.trigger_reason,
            "status": r.status,
        })
    return result


async def get_upcoming_revisions(exam_id: PydanticObjectId, days_ahead: int = 7) -> list[dict]:
    """Upcoming revisions in the next N days (for the RevisionQueuePage upcoming section)."""
    today = date.today()
    future = today + timedelta(days=days_ahead)
    revisions = await RevisionSchedule.find({
        "exam_id": exam_id,
        "status": "pending",
        "scheduled_date": {"$gt": str(today), "$lte": str(future)},
    }).sort("scheduled_date").to_list()

    return [
        {
            "id": str(r.id),
            "topic_name": r.topic_name,
            "revision_label": f"Revision {r.revision_number}/5" if r.revision_number > 0 else "Extra Revision",
            "scheduled_date": str(r.scheduled_date),
            "days_until": (r.scheduled_date - today).days,
            "trigger_reason": r.trigger_reason,
        }
        for r in revisions
    ]

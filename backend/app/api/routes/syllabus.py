from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks
from beanie import PydanticObjectId

from app.models.exam import Exam
from app.models.topic import Topic
from app.models.raw_syllabus import RawSyllabusUpload
from app.models.user import User
from app.schemas.topic import (
    TopicResponse, TopicUpdate, SyllabusUploadRequest,
    SyllabusUploadResponse, EnrichStatusResponse,
)
from app.services.topic_service import get_topic_tree, reparent_topic
from app.services.ai.syllabus_parser import parse_syllabus
from app.services.ai.difficulty_estimator import enrich_topics
from app.services.ai.logging_wrapper import log_ai_call
from app.services.topic_service import insert_topic_tree
from app.api.deps import get_current_user, get_exam_for_user
from app.core.exceptions import NotFoundError, AIParsingError
from app.services.ai.client import HEAVY_MODEL

router = APIRouter(tags=["syllabus & topics"])


# ── Syllabus upload ───────────────────────────────────────────────────────────

@router.post("/exams/{exam_id}/syllabus", response_model=SyllabusUploadResponse, status_code=201)
async def upload_syllabus(
    body: SyllabusUploadRequest,
    exam: Exam = Depends(get_exam_for_user),
):
    """Step A — Save raw text. No AI call yet."""
    upload = RawSyllabusUpload(exam_id=exam.id, raw_text=body.raw_text)
    await upload.insert()
    return SyllabusUploadResponse(
        upload_id=str(upload.id),
        parsed_status=upload.parsed_status,
    )


@router.get("/syllabus-uploads/{upload_id}/status", response_model=SyllabusUploadResponse)
async def get_upload_status(
    upload_id: str,
    current_user: User = Depends(get_current_user),
):
    """Poll this endpoint while the frontend shows a loading state."""
    upload = await RawSyllabusUpload.get(PydanticObjectId(upload_id))
    if not upload:
        raise NotFoundError("Upload not found")
    return SyllabusUploadResponse(
        upload_id=str(upload.id),
        parsed_status=upload.parsed_status,
    )


async def _run_parse(upload_id: str, exam_name: str, exam_id: PydanticObjectId, user_id: PydanticObjectId):
    """Background task: call AI, insert tree, update status."""
    upload = await RawSyllabusUpload.get(PydanticObjectId(upload_id))
    if not upload:
        return

    try:
        async def _do_parse():
            return await parse_syllabus(exam_name, upload.raw_text)

        parsed = await log_ai_call(
            agent_type="syllabus_parser",
            user_id=user_id,
            exam_id=exam_id,
            input_payload={"exam_name": exam_name, "raw_text": upload.raw_text[:500]},
            model_used=HEAVY_MODEL,
            fn=_do_parse,
        )
        # Delete any existing topics for this exam first (re-parse scenario)
        await Topic.find(Topic.exam_id == exam_id).delete()
        await insert_topic_tree(exam_id=exam_id, nodes=parsed.topics)
        await upload.set({
            "parsed_status": "success",
            "ai_model_used": HEAVY_MODEL,
        })
    except Exception as e:
        await upload.set({
            "parsed_status": "failed",
            "error_detail": str(e)[:500],
        })


@router.post("/syllabus-uploads/{upload_id}/parse", status_code=202)
async def trigger_parse(
    upload_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Step B — Trigger AI parsing in the background. Frontend polls /status."""
    upload = await RawSyllabusUpload.get(PydanticObjectId(upload_id))
    if not upload:
        raise NotFoundError("Upload not found")

    exam = await Exam.get(upload.exam_id)
    if not exam or exam.user_id != current_user.id:
        raise NotFoundError("Exam not found")

    background_tasks.add_task(
        _run_parse, upload_id, exam.name, exam.id, current_user.id
    )
    return {"message": "Parsing started", "upload_id": upload_id}


# ── Topic tree retrieval ──────────────────────────────────────────────────────

@router.get("/exams/{exam_id}/topics", response_model=list[TopicResponse])
async def get_topics(exam: Exam = Depends(get_exam_for_user)):
    """Step C — Return the full nested topic tree. Used for review/edit."""
    return await get_topic_tree(exam.id)


# ── Topic CRUD (review & edit) ────────────────────────────────────────────────

@router.patch("/topics/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: str,
    body: TopicUpdate,
    current_user: User = Depends(get_current_user),
):
    topic = await Topic.get(PydanticObjectId(topic_id))
    if not topic:
        raise NotFoundError("Topic not found")
    # Ownership: verify via exam
    exam = await Exam.get(topic.exam_id)
    if not exam or exam.user_id != current_user.id:
        raise NotFoundError("Topic not found")

    update_data = {"updated_at": datetime.now(timezone.utc)}

    if body.name is not None:
        update_data["name"] = body.name

    if body.order_index is not None:
        update_data["order_index"] = body.order_index

    if body.status is not None:
        update_data["status"] = body.status

    if body.parent_id is not None:
        new_parent = PydanticObjectId(body.parent_id) if body.parent_id != "null" else None
        await reparent_topic(topic, new_parent)
    else:
        await topic.set(update_data)

    # Return updated topic as flat TopicResponse (not full tree)
    updated = await Topic.get(topic.id)
    tree = await get_topic_tree(exam.id)
    # Find and return the specific node from the tree
    def find_node(nodes, tid):
        for n in nodes:
            if n.id == tid:
                return n
            found = find_node(n.children, tid)
            if found:
                return found
    node = find_node(tree, topic_id)
    return node or TopicResponse(
        id=str(updated.id), exam_id=str(updated.exam_id),
        parent_id=str(updated.parent_id) if updated.parent_id else None,
        name=updated.name, depth=updated.depth, order_index=updated.order_index,
        is_leaf=updated.is_leaf, difficulty=updated.difficulty,
        estimated_hours=updated.estimated_hours, weightage=updated.weightage,
        prerequisite_topic_id=str(updated.prerequisite_topic_id) if updated.prerequisite_topic_id else None,
        status=updated.status, completion_pct=updated.completion_pct, children=[],
    )


@router.delete("/topics/{topic_id}", status_code=204)
async def delete_topic(
    topic_id: str,
    current_user: User = Depends(get_current_user),
):
    topic = await Topic.get(PydanticObjectId(topic_id))
    if not topic:
        raise NotFoundError("Topic not found")
    exam = await Exam.get(topic.exam_id)
    if not exam or exam.user_id != current_user.id:
        raise NotFoundError("Topic not found")

    # Delete topic and all its descendants
    descendant_ids = [t.id for t in await Topic.find(
        {"ancestors": topic.id}
    ).to_list()]
    ids_to_delete = [topic.id] + descendant_ids
    await Topic.find({"_id": {"$in": ids_to_delete}}).delete()


# ── Enrichment ────────────────────────────────────────────────────────────────

async def _run_enrich(exam_id: PydanticObjectId, exam_name: str, experience_level: str, user_id: PydanticObjectId):
    """Background task for enrichment."""
    async def _do_enrich():
        return await enrich_topics(exam_id, exam_name, experience_level)

    await log_ai_call(
        agent_type="difficulty_estimator",
        user_id=user_id,
        exam_id=exam_id,
        input_payload={"exam_id": str(exam_id), "exam_name": exam_name},
        model_used=HEAVY_MODEL,
        fn=_do_enrich,
    )


@router.post("/exams/{exam_id}/enrich-topics", response_model=EnrichStatusResponse, status_code=202)
async def trigger_enrichment(
    background_tasks: BackgroundTasks,
    exam: Exam = Depends(get_exam_for_user),
    current_user: User = Depends(get_current_user),
):
    """Step D — User confirms tree is correct, trigger AI enrichment."""
    background_tasks.add_task(
        _run_enrich, exam.id, exam.name, exam.experience_level, current_user.id
    )
    return EnrichStatusResponse(exam_id=str(exam.id), enriched_count=0, failed_count=0)

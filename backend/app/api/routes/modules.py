"""
Module 2 API Routes — Module Start, Plan Retrieval, Day Editing.
All endpoints verified against exam ownership before acting.
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from beanie import PydanticObjectId

from app.api.deps import CurrentUser
from app.models.exam import Exam
from app.models.topic import Topic
from app.models.module_start import ModuleStart
from app.models.module_plan import ModulePlan
from app.models.module_plan_day import ModulePlanDay
from app.models.module_resource import ModuleResource
from app.schemas.module_start import ModuleStartRequest, ModuleStartStatusResponse, ModuleStartResponse
from app.schemas.module_plan import (
    ModuleDetailResponse, ModulePlanResponse, PlanDayResponse,
    ResourceResponse, DayUpdateRequest,
)
from app.services import module_service

router = APIRouter(prefix="/modules", tags=["modules"])


# ── Ownership helpers ─────────────────────────────────────────────────────────

async def _get_owned_module_start(module_id: str, user: object) -> ModuleStart:
    mid = PydanticObjectId(module_id)
    ms = await ModuleStart.get(mid)
    if not ms:
        raise HTTPException(status_code=404, detail="Module not found")
    exam = await Exam.get(ms.exam_id)
    if not exam or str(exam.user_id) != str(user.id):
        raise HTTPException(status_code=404, detail="Module not found")
    return ms


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
async def start_module(
    body: ModuleStartRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
):
    """
    Kick off the 2-stage pipeline for a topic.
    Returns immediately with module_start_id; frontend polls /status.
    """
    topic_id = PydanticObjectId(body.topic_id)
    topic = await Topic.get(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Verify exam ownership
    exam = await Exam.get(topic.exam_id)
    if not exam or str(exam.user_id) != str(user.id):
        raise HTTPException(status_code=404, detail="Topic not found")

    module_start = ModuleStart(
        exam_id=topic.exam_id,
        topic_id=topic_id,
        raw_input=body.raw_input,
        daily_hours_available=body.daily_hours_available,
        expected_hours=body.expected_hours,
        status="planning",
    )
    await module_start.insert()

    background_tasks.add_task(
        module_service.run_pipeline,
        module_start_id=module_start.id,
        user_id=user.id,
    )

    return {"module_start_id": str(module_start.id)}


@router.get("/{module_id}/status", response_model=ModuleStartStatusResponse)
async def get_module_status(module_id: str, user: CurrentUser):
    """Poll this while the pipeline runs. Returns status + error_detail if failed."""
    ms = await _get_owned_module_start(module_id, user)
    return ModuleStartStatusResponse(
        id=str(ms.id),
        status=ms.status,
        error_detail=ms.error_detail,
    )


@router.get("/{module_id}/plan", response_model=ModulePlanResponse)
async def get_module_plan(module_id: str, user: CurrentUser):
    """Return the full plan + days once status is 'active'."""
    ms = await _get_owned_module_start(module_id, user)
    if ms.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Plan not ready yet. Current status: {ms.status}"
        )
    plan = await ModulePlan.find_one(ModulePlan.module_start_id == ms.id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    days = await ModulePlanDay.find(
        ModulePlanDay.module_plan_id == plan.id
    ).sort("day_number").to_list()

    return ModulePlanResponse(
        id=str(plan.id),
        module_start_id=str(plan.module_start_id),
        total_days=plan.total_days,
        summary=plan.summary,
        is_accepted=plan.is_accepted,
        generated_at=plan.generated_at,
        days=[
            PlanDayResponse(
                id=str(d.id),
                day_number=d.day_number,
                planned_date=d.planned_date,
                focus_topics=d.focus_topics,
                planned_hours=d.planned_hours,
                planned_resources=d.planned_resources,
                goals=d.goals,
                status=d.status,
                actual_hours=d.actual_hours,
                notes=d.notes,
            )
            for d in days
        ],
    )


@router.get("/{module_id}", response_model=ModuleDetailResponse)
async def get_module_detail(module_id: str, user: CurrentUser):
    """Full module detail: status + resources + plan (if ready)."""
    ms = await _get_owned_module_start(module_id, user)
    resources = await ModuleResource.find(
        ModuleResource.module_start_id == ms.id
    ).to_list()

    plan_response = None
    if ms.status == "active":
        plan = await ModulePlan.find_one(ModulePlan.module_start_id == ms.id)
        if plan:
            days = await ModulePlanDay.find(
                ModulePlanDay.module_plan_id == plan.id
            ).sort("day_number").to_list()
            plan_response = ModulePlanResponse(
                id=str(plan.id),
                module_start_id=str(plan.module_start_id),
                total_days=plan.total_days,
                summary=plan.summary,
                is_accepted=plan.is_accepted,
                generated_at=plan.generated_at,
                days=[
                    PlanDayResponse(
                        id=str(d.id), day_number=d.day_number, planned_date=d.planned_date,
                        focus_topics=d.focus_topics, planned_hours=d.planned_hours,
                        planned_resources=d.planned_resources, goals=d.goals,
                        status=d.status, actual_hours=d.actual_hours, notes=d.notes,
                    )
                    for d in days
                ],
            )

    return ModuleDetailResponse(
        module_start={
            "id": str(ms.id), "exam_id": str(ms.exam_id), "topic_id": str(ms.topic_id),
            "status": ms.status, "error_detail": ms.error_detail,
            "daily_hours_available": ms.daily_hours_available,
            "expected_hours": ms.expected_hours, "started_at": ms.started_at.isoformat(),
        },
        resources=[
            ResourceResponse(
                id=str(r.id), type=r.type, title=r.title, source_name=r.source_name,
                url=r.url, total_units=r.total_units, units_planned=r.units_planned,
                units_completed=r.units_completed,
            )
            for r in resources
        ],
        plan=plan_response,
    )


@router.post("/{module_id}/retry-plan", status_code=status.HTTP_202_ACCEPTED)
async def retry_plan(module_id: str, background_tasks: BackgroundTasks, user: CurrentUser):
    """Re-run Stage 2 only (Stage 1 resources preserved). Use when status='planning_failed'."""
    ms = await _get_owned_module_start(module_id, user)
    if ms.status not in ("planning_failed", "active"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry. Status must be 'planning_failed', got '{ms.status}'"
        )
    background_tasks.add_task(
        module_service.retry_plan_stage2,
        module_start_id=ms.id,
        user_id=user.id,
    )
    return {"message": "Retry started. Poll /status for updates."}


@router.patch("/{module_id}/plan/days/{day_id}")
async def update_plan_day(
    module_id: str, day_id: str, body: DayUpdateRequest, user: CurrentUser
):
    """User manually adjusts a day (hours, resources, goals) before accepting the plan."""
    ms = await _get_owned_module_start(module_id, user)
    day = await ModulePlanDay.get(PydanticObjectId(day_id))
    if not day:
        raise HTTPException(status_code=404, detail="Day not found")

    # Verify day belongs to this module's plan
    plan = await ModulePlan.find_one(ModulePlan.module_start_id == ms.id)
    if not plan or day.module_plan_id != plan.id:
        raise HTTPException(status_code=404, detail="Day not found")

    update = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if update:
        await day.set(update)

    return {"message": "Day updated"}


@router.post("/{module_id}/accept")
async def accept_plan(module_id: str, user: CurrentUser):
    """User explicitly accepts the plan — marks it as ready for Module 3 to execute."""
    ms = await _get_owned_module_start(module_id, user)
    if ms.status != "active":
        raise HTTPException(status_code=400, detail="Plan must be active to accept")

    plan = await ModulePlan.find_one(ModulePlan.module_start_id == ms.id)
    if plan:
        await plan.set({"is_accepted": True})

    return {"message": "Plan accepted and ready for execution"}


# ── Exam-scoped list ──────────────────────────────────────────────────────────

exam_modules_router = APIRouter(tags=["modules"])


@exam_modules_router.get("/exams/{exam_id}/modules")
async def list_exam_modules(exam_id: str, user: CurrentUser):
    """List all module starts for an exam (active + past)."""
    eid = PydanticObjectId(exam_id)
    exam = await Exam.get(eid)
    if not exam or str(exam.user_id) != str(user.id):
        raise HTTPException(status_code=404, detail="Exam not found")

    modules = await ModuleStart.find(
        ModuleStart.exam_id == eid
    ).sort("-started_at").to_list()

    # Fetch topic names for display
    topic_ids = [m.topic_id for m in modules]
    topics = {str(t.id): t.name for t in await Topic.find({"_id": {"$in": topic_ids}}).to_list()}

    return [
        {
            "id": str(m.id),
            "topic_id": str(m.topic_id),
            "topic_name": topics.get(str(m.topic_id), "Unknown"),
            "status": m.status,
            "daily_hours_available": m.daily_hours_available,
            "started_at": m.started_at.isoformat(),
        }
        for m in modules
    ]

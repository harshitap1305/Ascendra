"""
Module 2 orchestration service.
The full 2-stage pipeline lives here — route handlers stay thin.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from beanie import PydanticObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from app.models.exam import Exam
from app.models.topic import Topic
from app.models.module_start import ModuleStart
from app.models.module_plan import ModulePlan
from app.models.module_plan_day import ModulePlanDay
from app.models.module_resource import ModuleResource
from app.schemas.ai_resource_parser import ParsedResourcesResponse
from app.schemas.ai_planner import MasterPlanResponse
from app.services.ai import resource_parser, planner
from app.services.ai.planner import PlannerContext, PlanConstraintError
from app.services.ai.logging_wrapper import log_ai_call
from app.services.ai.client import HEAVY_MODEL
from app.services import topic_service
from app.core.exceptions import NotFoundError


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _persist_resources(
    module_start: ModuleStart,
    parsed: ParsedResourcesResponse,
) -> list[dict]:
    """Insert ModuleResource documents and return plain dicts for context building."""
    resource_dicts = []
    for r in parsed.resources:
        doc = ModuleResource(
            module_start_id=module_start.id,
            exam_id=module_start.exam_id,
            topic_id=module_start.topic_id,
            type=r.type,
            title=r.title,
            source_name=r.source_name,
            url=r.url,
            total_units=r.total_units,
            units_planned=r.total_units,
        )
        await doc.insert()
        resource_dicts.append({
            "type": r.type,
            "title": r.title,
            "source_name": r.source_name,
            "total_units": r.total_units,
        })
    return resource_dicts


async def _persist_plan(
    module_start: ModuleStart,
    plan: MasterPlanResponse,
) -> ModulePlan:
    """Persist the module_plan + all module_plan_days. Uses an in-memory approach
    since Beanie doesn't expose Motor sessions directly; failures are caught by the caller."""
    plan_doc = ModulePlan(
        module_start_id=module_start.id,
        total_days=plan.total_days,
        summary=plan.summary,
        ai_raw_response=plan.model_dump(),
    )
    await plan_doc.insert()

    start_date = module_start.started_at.date()
    for day in plan.days:
        day_doc = ModulePlanDay(
            module_plan_id=plan_doc.id,
            day_number=day.day_number,
            planned_date=start_date + timedelta(days=day.day_number - 1),
            focus_topics=day.focus_topics,
            planned_hours=day.planned_hours,
            planned_resources=day.resources_to_cover,
            goals=day.goals,
        )
        await day_doc.insert()

    return plan_doc


async def _build_planning_context(
    module_start: ModuleStart,
    topic: Topic,
    exam: Exam,
    resource_dicts: list[dict],
    subtopics: list[dict],
    overall_completion: float,
) -> PlannerContext:
    """Assemble the full student model context for the Planner agent."""
    from datetime import date
    days_remaining = (
        (exam.exam_date - date.today()).days if exam.exam_date else None
    )
    return PlannerContext(
        exam_name=exam.name,
        exam_date=exam.exam_date,
        days_remaining=days_remaining,
        overall_completion_pct=overall_completion,
        experience_level=exam.experience_level,
        topic_name=topic.name,
        topic_difficulty=topic.difficulty,
        topic_weightage=topic.weightage,
        subtopics=subtopics,
        raw_module_input_text=module_start.raw_input,
        module_resources=resource_dicts,
        daily_hours_available=module_start.daily_hours_available,
        expected_hours=module_start.expected_hours,
    )


# ── Background Pipeline ───────────────────────────────────────────────────────

async def run_pipeline(module_start_id: PydanticObjectId, user_id: PydanticObjectId) -> None:
    """
    Full 2-stage pipeline run as a FastAPI BackgroundTask.
    Stage 1: Resource parsing + context data fetching (parallel)
    Stage 2: Master plan generation (sequential, needs Stage 1 output)
    """
    module_start = await ModuleStart.get(module_start_id)
    if not module_start:
        return

    topic = await Topic.get(module_start.topic_id)
    exam = await Exam.get(module_start.exam_id)
    if not topic or not exam:
        await module_start.set({"status": "planning_failed", "error_detail": "Topic or exam not found"})
        return

    # ── Stage 1 + parallel context fetching ──────────────────────────────────
    try:
        async def _parse():
            return await resource_parser.parse_resources(module_start.raw_input, topic.name)

        parsed_resources, subtopics, overall_completion = await asyncio.gather(
            log_ai_call(
                agent_type="resource_parser",
                user_id=user_id,
                exam_id=module_start.exam_id,
                input_payload={"topic_name": topic.name, "raw_input": module_start.raw_input[:500]},
                model_used=HEAVY_MODEL,
                fn=_parse,
            ),
            topic_service.get_topic_subtree(topic.id),
            topic_service.get_exam_completion_pct(module_start.exam_id),
        )
        resource_dicts = await _persist_resources(module_start, parsed_resources)

    except Exception as e:
        await module_start.set({
            "status": "planning_failed",
            "error_detail": f"Resource parsing failed: {str(e)[:400]}",
            "updated_at": datetime.now(timezone.utc),
        })
        return

    # ── Stage 2: Generate master plan ────────────────────────────────────────
    try:
        ctx = await _build_planning_context(
            module_start, topic, exam, resource_dicts, subtopics, overall_completion
        )

        async def _plan():
            return await planner.generate_plan(ctx)

        generated_plan = await log_ai_call(
            agent_type="planner",
            user_id=user_id,
            exam_id=module_start.exam_id,
            input_payload={"topic_name": topic.name, "days_remaining": ctx.days_remaining},
            model_used=HEAVY_MODEL,
            fn=_plan,
        )
        await _persist_plan(module_start, generated_plan)
        await module_start.set({
            "status": "active",
            "updated_at": datetime.now(timezone.utc),
        })

    except (PlanConstraintError, Exception) as e:
        # Stage 1 resources are preserved — user can retry Stage 2
        await module_start.set({
            "status": "planning_failed",
            "error_detail": f"Plan generation failed: {str(e)[:400]}",
            "updated_at": datetime.now(timezone.utc),
        })


async def retry_plan_stage2(module_start_id: PydanticObjectId, user_id: PydanticObjectId) -> None:
    """
    Re-run only Stage 2 using already-parsed resources from Stage 1.
    Deletes any existing failed plan before re-generating.
    """
    module_start = await ModuleStart.get(module_start_id)
    if not module_start or module_start.status not in ("planning_failed", "active"):
        return

    topic = await Topic.get(module_start.topic_id)
    exam = await Exam.get(module_start.exam_id)
    if not topic or not exam:
        return

    # Reset status to planning
    await module_start.set({
        "status": "planning",
        "error_detail": None,
        "updated_at": datetime.now(timezone.utc),
    })

    # Delete any existing plan for this module start
    existing_plan = await ModulePlan.find_one(ModulePlan.module_start_id == module_start_id)
    if existing_plan:
        await ModulePlanDay.find(ModulePlanDay.module_plan_id == existing_plan.id).delete()
        await existing_plan.delete()

    # Fetch existing resources
    resources = await ModuleResource.find(
        ModuleResource.module_start_id == module_start_id
    ).to_list()
    resource_dicts = [
        {"type": r.type, "title": r.title, "source_name": r.source_name, "total_units": r.total_units}
        for r in resources
    ]

    subtopics, overall_completion = await asyncio.gather(
        topic_service.get_topic_subtree(topic.id),
        topic_service.get_exam_completion_pct(module_start.exam_id),
    )

    try:
        ctx = await _build_planning_context(
            module_start, topic, exam, resource_dicts, subtopics, overall_completion
        )

        async def _plan():
            return await planner.generate_plan(ctx)

        generated_plan = await log_ai_call(
            agent_type="planner",
            user_id=user_id,
            exam_id=module_start.exam_id,
            input_payload={"topic_name": topic.name, "retry": True},
            model_used=HEAVY_MODEL,
            fn=_plan,
        )
        await _persist_plan(module_start, generated_plan)
        await module_start.set({
            "status": "active",
            "updated_at": datetime.now(timezone.utc),
        })

    except Exception as e:
        await module_start.set({
            "status": "planning_failed",
            "error_detail": f"Retry failed: {str(e)[:400]}",
            "updated_at": datetime.now(timezone.utc),
        })

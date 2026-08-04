"""
Daily service — Module 3 core orchestration.
Pipeline A: generate_daily_plan / get_or_generate_today_plan
Pipeline B: process_checkin (progress → study logs → pace → feedback → replanning)
"""
import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from beanie import PydanticObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

from app.models.exam import Exam
from app.models.topic import Topic
from app.models.module_start import ModuleStart
from app.models.module_plan import ModulePlan
from app.models.module_plan_day import ModulePlanDay
from app.models.daily_plan import DailyPlan
from app.models.daily_report import DailyReport
from app.models.study_log import StudyLog
from app.models.feedback import Feedback
from app.services.ai import daily_planner as daily_planner_agent
from app.services.ai import progress_analyzer as progress_agent
from app.services.ai import feedback_generator as feedback_agent
from app.services.ai.client import HEAVY_MODEL
from app.services.ai.logging_wrapper import log_ai_call
from app.services import replanning_service
from app.services.topic_service import recalculate_completion
from app.services import revision_service  # Module 4 — spaced revision hook


# ── Pipeline A — Daily Plan Generation ───────────────────────────────────────

async def get_or_generate_today_plan(
    module_start_id: PydanticObjectId,
    user_id: PydanticObjectId,
) -> Optional[DailyPlan]:
    """
    Lazy-generation fallback: return today's plan if it exists, otherwise generate it.
    This is race-safe via the unique (module_start_id, plan_date) index.
    """
    today = date.today()
    existing = await DailyPlan.find_one({
        "module_start_id": module_start_id,
        "plan_date": today,
    })
    if existing:
        return existing
    return await generate_daily_plan(module_start_id, user_id)


async def generate_daily_plan(
    module_start_id: PydanticObjectId,
    user_id: PydanticObjectId,
) -> Optional[DailyPlan]:
    """
    Generate today's daily plan from the master plan day.
    Called by APScheduler (batch) or lazily by get_or_generate_today_plan().
    """
    today = date.today()
    module_start = await ModuleStart.get(module_start_id)
    if not module_start or module_start.status != "active":
        return None

    # Find today's master plan day by planned_date
    plan = await ModulePlan.find_one(ModulePlan.module_start_id == module_start_id)
    if not plan:
        return None

    plan_day = await ModulePlanDay.find_one({
        "module_plan_id": plan.id,
        "planned_date": today,
    })
    if not plan_day:
        return None  # No plan day for today — module window ended or not started

    # Fetch carry-over tasks from yesterday's unfinished check-in
    carry_over_tasks = await _get_carry_over_tasks(module_start_id, today)

    topic = await Topic.get(module_start.topic_id)
    topic_name = topic.name if topic else "Study Topic"

    async def _generate():
        return await daily_planner_agent.generate_daily_plan(
            topic_name=topic_name,
            day_number=plan_day.day_number,
            total_days=plan.total_days,
            focus_topics=plan_day.focus_topics,
            planned_hours=plan_day.planned_hours,
            planned_resources=plan_day.planned_resources,
            goals=plan_day.goals,
            daily_hours_available=module_start.daily_hours_available,
            carry_over_tasks=carry_over_tasks,
        )

    ai_response = await log_ai_call(
        agent_type="daily_planner",
        user_id=user_id,
        exam_id=module_start.exam_id,
        input_payload={"topic_name": topic_name, "day_number": plan_day.day_number},
        model_used=HEAVY_MODEL,
        fn=_generate,
    )

    daily_plan = DailyPlan(
        module_start_id=module_start_id,
        module_plan_day_id=plan_day.id,
        plan_date=today,
        tasks=[t.model_dump() for t in ai_response.tasks],
        planned_hours=ai_response.planned_hours,
        daily_goal=ai_response.daily_goal,
        carry_over_tasks=carry_over_tasks,
        ai_raw_response=ai_response.model_dump(),
    )

    try:
        await daily_plan.insert()
    except DuplicateKeyError:
        # Scheduler and lazy-gen raced — return the already-existing plan
        return await DailyPlan.find_one({
            "module_start_id": module_start_id,
            "plan_date": today,
        })

    return daily_plan


async def _get_carry_over_tasks(
    module_start_id: PydanticObjectId,
    today: date,
) -> list[dict]:
    """
    Carry-over logic (production behavior):
    - After a real check-in: pending_tasks from that check-in carry over
    - After a skip: ALL tasks from the skipped day carry over (day off means work still pending)
    """
    yesterday = today - timedelta(days=1)

    # Check if yesterday had a check-in
    yesterday_report = await DailyReport.find_one({
        "module_start_id": module_start_id,
        "plan_date": yesterday,
    })
    if yesterday_report:
        return yesterday_report.pending_tasks or []

    # Check if yesterday was skipped
    yesterday_plan = await DailyPlan.find_one({
        "module_start_id": module_start_id,
        "plan_date": yesterday,
    })
    if yesterday_plan and yesterday_plan.status == "skipped":
        # Skip = carry over all tasks (user took a day off, work is still pending)
        return yesterday_plan.tasks or []

    return []


# ── Pipeline B — Check-in, Progress, Feedback, Replanning ────────────────────

async def process_checkin(
    daily_plan: DailyPlan,
    raw_text: str,
    user_id: PydanticObjectId,
) -> Feedback:
    """
    Full Pipeline B:
    1. Agent 6 — extract structured progress from raw text
    2. Persist daily_report + study_logs
    3. Update topic completion via recalculate_completion rollup
    4. Update module_plan_day status
    5. Compute PaceContext (deterministic)
    6. Agent 7 — generate mentor feedback
    7. Deterministic replanning (always runs)
    8. Persist feedback
    """
    module_start = await ModuleStart.get(daily_plan.module_start_id)
    exam = await Exam.get(module_start.exam_id)

    # ── Stage 1: Progress Analysis ──────────────────────────────────────────
    async def _analyze():
        return await progress_agent.analyze_progress(daily_plan.tasks, raw_text)

    analysis = await log_ai_call(
        agent_type="progress_analyzer",
        user_id=user_id,
        exam_id=module_start.exam_id,
        input_payload={"task_count": len(daily_plan.tasks), "text_len": len(raw_text)},
        model_used=HEAVY_MODEL,
        fn=_analyze,
    )

    # ── Stage 2: Persist report + study logs ────────────────────────────────
    completed = [r for r in analysis.task_results if r.status == "completed"]
    pending = [r for r in analysis.task_results if r.status in ("partial", "skipped", "not_mentioned")]

    # Map task_ref → task dict for topic resolution
    task_map = {t["task_ref"]: t for t in daily_plan.tasks}

    report = DailyReport(
        daily_plan_id=daily_plan.id,
        module_start_id=daily_plan.module_start_id,
        plan_date=daily_plan.plan_date,
        raw_text=raw_text,
        completed_tasks=[task_map[r.task_ref] for r in completed if r.task_ref in task_map],
        pending_tasks=[task_map[r.task_ref] for r in pending if r.task_ref in task_map],
        actual_hours=analysis.actual_hours_spent,
        confidence_rating=analysis.confidence_rating,
        mood_note=analysis.mood_note,
        delay_reason=analysis.delay_reason,
    )
    await report.insert()

    # ── Stage 3: Update topic completion for each completed/partial task ────
    topic_ids_updated: set[PydanticObjectId] = set()
    for result in analysis.task_results:
        if result.status not in ("completed", "partial"):
            continue
        task = task_map.get(result.task_ref)
        if not task:
            continue
        topic = await _resolve_topic_by_name(task.get("topic_name", ""), module_start.topic_id)
        if topic:
            # Update topic status
            new_status = "completed" if result.status == "completed" else "in_progress"
            await topic.set({
                "status": new_status,
                "completion_pct": 100.0 if result.status == "completed" else topic.completion_pct,
                "updated_at": datetime.now(timezone.utc),
            })
            # Persist study log
            await StudyLog(
                daily_report_id=report.id,
                topic_id=topic.id,
                module_start_id=daily_plan.module_start_id,
                status_change=new_status,
                units_completed=result.units_completed,
            ).insert()
            topic_ids_updated.add(topic.id)

    # Bubble up completion to ancestors + trigger Module 4 revision scheduling
    for topic_id in topic_ids_updated:
        topic = await Topic.get(topic_id)
        if topic and topic.parent_id:
            await recalculate_completion(topic.parent_id)
        # Module 4 hook: when a leaf topic completes, schedule spaced revisions
        if topic and topic.is_leaf and topic.status == "completed":
            await revision_service.schedule_revisions_for_topic(topic)

    # ── Stage 4: Update module_plan_day status ──────────────────────────────
    plan_day = await ModulePlanDay.get(daily_plan.module_plan_day_id)
    if plan_day:
        all_done = all(r.status == "completed" for r in analysis.task_results)
        new_day_status = "done" if all_done else "partially_completed"
        await plan_day.set({
            "status": new_day_status,
            "actual_hours": analysis.actual_hours_spent,
        })

    # Update daily_plan status too
    all_done = analysis.overall_completion_today >= 0.95
    await daily_plan.set({
        "status": "completed" if all_done else "partially_completed",
    })

    # ── Stage 5: Compute PaceContext (pure backend) ─────────────────────────
    pace_ctx = await _compute_pace_context(
        module_start, exam, analysis.overall_completion_today
    )

    # ── Stage 6: Generate feedback (Agent 7) ────────────────────────────────
    completed_refs = [r.task_ref for r in completed]
    today_summary = _build_today_summary(daily_plan.tasks, analysis.task_results)

    async def _feedback():
        return await feedback_agent.generate_feedback(
            topic_name=(await Topic.get(module_start.topic_id)).name if await Topic.get(module_start.topic_id) else "Topic",
            exam_name=exam.name,
            today_tasks_summary=today_summary,
            completed_count=len(completed),
            total_count=len(daily_plan.tasks),
            pace_context=pace_ctx,
        )

    feedback_response = await log_ai_call(
        agent_type="feedback_generator",
        user_id=user_id,
        exam_id=module_start.exam_id,
        input_payload={"completion_fraction": analysis.overall_completion_today},
        model_used=HEAVY_MODEL,
        fn=_feedback,
    )

    # ── Stage 7: Deterministic replanning (always runs) ─────────────────────
    plan_adjusted, adjustment_summary = await replanning_service.redistribute(
        module_start_id=daily_plan.module_start_id,
        today_completion_fraction=analysis.overall_completion_today,
    )

    # ── Stage 8: Persist feedback ────────────────────────────────────────────
    feedback = Feedback(
        daily_report_id=report.id,
        module_start_id=daily_plan.module_start_id,
        exam_id=module_start.exam_id,
        performance_summary=feedback_response.performance_summary,
        pace_status=feedback_response.pace_status,
        risk_level=feedback_response.risk_level,
        suggestions=feedback_response.suggestions,
        motivational_note=feedback_response.motivational_note,
        confidence_display=analysis.confidence_rating,
        plan_adjusted=plan_adjusted,
        adjustment_summary=adjustment_summary,
        ai_raw_response=feedback_response.model_dump(),
    )
    await feedback.insert()

    # Check if module is complete (all plan days done)
    await _check_module_completion(module_start, plan)

    return feedback


async def skip_today(daily_plan: DailyPlan) -> None:
    """Mark today as skipped. Tasks carry over automatically to tomorrow's plan generation."""
    await daily_plan.set({"status": "skipped"})
    # Also mark the module_plan_day as skipped
    plan_day = await ModulePlanDay.get(daily_plan.module_plan_day_id)
    if plan_day:
        await plan_day.set({"status": "skipped"})


# ── PaceContext (pure Python — no AI) ─────────────────────────────────────────

async def _compute_pace_context(
    module_start: ModuleStart,
    exam: Exam,
    today_completion_fraction: float,
) -> dict:
    """
    Compute all pace metrics from DB data. No AI involved.
    Returns a plain dict passed directly to the feedback agent.
    """
    # Fetch the plan
    plan = await ModulePlan.find_one(ModulePlan.module_start_id == module_start.id)
    plan_days = []
    if plan:
        plan_days = await ModulePlanDay.find(ModulePlanDay.module_plan_id == plan.id).to_list()

    days_elapsed = sum(1 for d in plan_days if d.status in ("done", "adjusted", "partially_completed", "skipped"))
    days_total = len(plan_days)
    days_remaining_in_module = days_total - days_elapsed

    # Sum planned hours for elapsed days
    planned_hours_so_far = sum(
        d.planned_hours for d in plan_days
        if d.status in ("done", "adjusted", "partially_completed")
    )

    # Sum actual hours from daily reports
    actual_hours_pipeline = [
        {"$match": {"module_start_id": module_start.id}},
        {"$group": {"_id": None, "total": {"$sum": "$actual_hours"}}},
    ]
    actual_results = await DailyReport.aggregate(actual_hours_pipeline).to_list()
    actual_hours_so_far = actual_results[0]["total"] if actual_results else 0.0
    if actual_hours_so_far is None:
        actual_hours_so_far = 0.0

    hours_delta = actual_hours_so_far - planned_hours_so_far

    # Topic and exam completion
    from app.services.topic_service import get_exam_completion_pct
    overall_exam_completion = await get_exam_completion_pct(module_start.exam_id)

    # Module topic completion
    topic = await Topic.get(module_start.topic_id)
    topic_completion = topic.completion_pct if topic else 0.0

    # Days until exam
    days_remaining_exam = None
    if exam and exam.exam_date:
        days_remaining_exam = (exam.exam_date - date.today()).days

    # Streak
    streak = await _compute_streak(module_start.id)

    return {
        "days_elapsed": days_elapsed,
        "days_total": days_total,
        "days_remaining_in_module": days_remaining_in_module,
        "planned_hours_so_far": round(planned_hours_so_far, 1),
        "actual_hours_so_far": round(actual_hours_so_far, 1),
        "hours_delta": round(hours_delta, 1),
        "topic_completion_pct": topic_completion,
        "overall_exam_completion_pct": overall_exam_completion,
        "days_remaining_exam": days_remaining_exam,
        "current_streak_days": streak,
        "today_completion_fraction": today_completion_fraction,
    }


async def _compute_streak(module_start_id: PydanticObjectId) -> int:
    """Count consecutive days with a submitted daily report going backwards from today."""
    today = date.today()
    streak = 0
    check_date = today
    while True:
        report = await DailyReport.find_one({
            "module_start_id": module_start_id,
            "plan_date": check_date,
        })
        if not report:
            break
        streak += 1
        check_date -= timedelta(days=1)
    return streak


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _resolve_topic_by_name(
    topic_name: str,
    root_topic_id: PydanticObjectId,
) -> Optional[Topic]:
    """Find a topic by name within the module's topic subtree."""
    if not topic_name:
        return None
    topic = await Topic.find_one({
        "ancestors": root_topic_id,
        "name": {"$regex": topic_name, "$options": "i"},
    })
    return topic


def _build_today_summary(tasks: list[dict], results: list) -> str:
    """Build a concise text summary of today's performance for the feedback agent."""
    lines = []
    for r in results:
        task = next((t for t in tasks if t.get("task_ref") == r.task_ref), None)
        if task:
            emoji = {"completed": "✓", "partial": "~", "skipped": "✗", "not_mentioned": "?"}.get(r.status, "?")
            lines.append(f"{emoji} {task['description']} ({r.status})")
    return "\n".join(lines) if lines else "No tasks reported"


async def _check_module_completion(module_start: ModuleStart, plan: Optional[ModulePlan]) -> None:
    """Mark module as completed when all plan days are done."""
    if not plan:
        return
    plan_days = await ModulePlanDay.find(ModulePlanDay.module_plan_id == plan.id).to_list()
    all_done = all(d.status in ("done", "adjusted", "skipped") for d in plan_days)
    if all_done and module_start.status == "active":
        await module_start.set({
            "status": "completed",
            "updated_at": datetime.now(timezone.utc),
        })


# ── Batch generation for scheduler ────────────────────────────────────────────

async def generate_all_daily_plans() -> None:
    """
    Called by APScheduler at 4:00 AM.
    Generates plans for all active modules. One failure does NOT stop others.
    """
    import logging
    logger = logging.getLogger(__name__)

    active_modules = await ModuleStart.find(ModuleStart.status == "active").to_list()
    semaphore = asyncio.Semaphore(5)  # max 5 concurrent AI calls

    async def _generate_one(ms: ModuleStart) -> None:
        async with semaphore:
            try:
                await generate_daily_plan(ms.id, ms.id)  # use module_start.id as proxy user_id for batch
            except Exception as e:
                logger.error(f"Daily plan generation failed for module {ms.id}: {e}")

    await asyncio.gather(*[_generate_one(m) for m in active_modules])

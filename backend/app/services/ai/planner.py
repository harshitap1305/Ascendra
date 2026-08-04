import json
from datetime import date
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

from app.schemas.ai_planner import MasterPlanResponse
from app.services.ai.client import call_groq, HEAVY_MODEL
from app.services.ai.validation import validate_with_retry

_PROMPT_PATH = Path(__file__).parent / "prompts" / "planner.txt"
SYSTEM_PROMPT = _PROMPT_PATH.read_text()


class PlannerContext(BaseModel):
    """Full student model passed to the Planner agent. Assembled fresh at generation time."""
    # Exam-level
    exam_name: str
    exam_date: Optional[date] = None
    days_remaining: Optional[int] = None
    overall_completion_pct: float
    experience_level: str

    # Topic-level (from Module 1 enrichment)
    topic_name: str
    topic_difficulty: Optional[str] = None
    topic_weightage: Optional[float] = None
    subtopics: list[dict]   # [{name, difficulty, estimated_hours, status}]

    # User's stated resources and time budget
    raw_module_input_text: str
    module_resources: list[dict]   # parsed by Agent 3
    daily_hours_available: float
    expected_hours: Optional[float] = None


class PlanConstraintError(Exception):
    pass


def _validate_plan_constraints(plan: MasterPlanResponse, ctx: PlannerContext) -> None:
    """
    Post-Pydantic business rule check.
    Pydantic confirms JSON shape; this confirms the plan is *logically sane*.
    Raises PlanConstraintError with a clear message if violated.
    """
    if ctx.days_remaining is not None and plan.total_days > ctx.days_remaining:
        raise PlanConstraintError(
            f"Generated plan spans {plan.total_days} days but only "
            f"{ctx.days_remaining} days remain before the exam. "
            f"Compress the plan to fit within {ctx.days_remaining} days."
        )
    for day in plan.days:
        limit = ctx.daily_hours_available * 1.1
        if day.planned_hours > limit:
            raise PlanConstraintError(
                f"Day {day.day_number} plans {day.planned_hours}h, exceeding "
                f"the {ctx.daily_hours_available}h daily budget by more than 10%. "
                f"Redistribute hours so no day exceeds {limit:.1f}h."
            )


def _build_user_message(ctx: PlannerContext) -> str:
    """Build the rich user message from the PlannerContext."""
    subtopics_str = json.dumps(ctx.subtopics, indent=2)
    resources_str = json.dumps(ctx.module_resources, indent=2)

    parts = [
        f"EXAM: {ctx.exam_name}",
        f"Experience level: {ctx.experience_level}",
        f"Overall exam completion: {ctx.overall_completion_pct:.1f}%",
    ]
    if ctx.exam_date:
        parts.append(f"Exam date: {ctx.exam_date}")
    if ctx.days_remaining is not None:
        parts.append(f"Days remaining until exam: {ctx.days_remaining}")

    parts += [
        f"\nTOPIC: {ctx.topic_name}",
    ]
    if ctx.topic_difficulty:
        parts.append(f"Topic difficulty: {ctx.topic_difficulty}")
    if ctx.topic_weightage is not None:
        parts.append(f"Topic weightage: {ctx.topic_weightage}%")

    parts += [
        f"\nSUBTOPICS (with difficulty and estimated hours):\n{subtopics_str}",
        f"\nSTUDENT'S RAW PLAN TEXT:\n\"\"\"\n{ctx.raw_module_input_text}\n\"\"\"",
        f"\nEXTRACTED RESOURCES:\n{resources_str}",
        f"\nDAILY HOURS AVAILABLE: {ctx.daily_hours_available}",
    ]
    if ctx.expected_hours is not None:
        parts.append(f"Student's expected total hours for this module: {ctx.expected_hours}")

    return "\n".join(parts)


async def generate_plan(ctx: PlannerContext) -> MasterPlanResponse:
    """
    Agent 4 — Generate a day-by-day master plan from the full student context.
    Three-layer validation:
      Layer 1: tenacity (network retry) inside call_groq
      Layer 2: Pydantic schema via validate_with_retry
      Layer 3: Business constraint check — retries once with violation appended
    """
    user_msg = _build_user_message(ctx)
    raw = await call_groq(SYSTEM_PROMPT, user_msg, model=HEAVY_MODEL)
    plan = await validate_with_retry(raw, MasterPlanResponse, SYSTEM_PROMPT, user_msg, HEAVY_MODEL)

    try:
        _validate_plan_constraints(plan, ctx)
    except PlanConstraintError as e:
        # Retry once with the constraint violation appended
        retry_msg = (
            f"{user_msg}\n\n"
            f"IMPORTANT: Your previous plan violated these constraints:\n{e}\n"
            f"Return a corrected plan as valid JSON only."
        )
        raw = await call_groq(SYSTEM_PROMPT, retry_msg, model=HEAVY_MODEL)
        plan = await validate_with_retry(raw, MasterPlanResponse, SYSTEM_PROMPT, retry_msg, HEAVY_MODEL)
        _validate_plan_constraints(plan, ctx)  # raises again if still broken → caller handles

    return plan

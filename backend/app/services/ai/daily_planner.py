import json
from pathlib import Path
from app.schemas.ai_daily_planner import DailyPlanResponse
from app.services.ai.client import call_groq, HEAVY_MODEL
from app.services.ai.validation import validate_with_retry

_PROMPT_PATH = Path(__file__).parent / "prompts" / "daily_planner.txt"
SYSTEM_PROMPT = _PROMPT_PATH.read_text()


async def generate_daily_plan(
    topic_name: str,
    day_number: int,
    total_days: int,
    focus_topics: list[str],
    planned_hours: float,
    planned_resources: list[dict],
    goals: str,
    daily_hours_available: float,
    carry_over_tasks: list[dict],
    yesterday_summary: str = "",
) -> DailyPlanResponse:
    """
    Agent 5 — Generate today's concrete task list from the master plan day.
    Carry-over tasks from previous day's unfinished work are incorporated.
    """
    carry_over_section = ""
    if carry_over_tasks:
        carry_over_section = (
            f"\nCarry-over tasks from yesterday (unfinished — must be in today's list):\n"
            f"{json.dumps(carry_over_tasks, indent=2)}"
        )

    if yesterday_summary:
        carry_over_section += f"\nYesterday's context: {yesterday_summary}"

    user_msg = (
        f"Topic: {topic_name}\n"
        f"Day {day_number} of {total_days}\n"
        f"Today's master plan:\n"
        f"  - Focus topics: {', '.join(focus_topics)}\n"
        f"  - Master plan goal: {goals}\n"
        f"  - Planned hours: {planned_hours}h\n"
        f"  - Resources for today:\n{json.dumps(planned_resources, indent=2)}\n"
        f"Daily hours available: {daily_hours_available}h"
        f"{carry_over_section}"
    )

    raw = await call_groq(SYSTEM_PROMPT, user_msg, model=HEAVY_MODEL)
    return await validate_with_retry(raw, DailyPlanResponse, SYSTEM_PROMPT, user_msg, HEAVY_MODEL)

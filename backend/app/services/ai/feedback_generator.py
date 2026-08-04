import json
from pathlib import Path
from app.schemas.ai_feedback import FeedbackResponse
from app.services.ai.client import call_groq, HEAVY_MODEL
from app.services.ai.validation import validate_with_retry

_PROMPT_PATH = Path(__file__).parent / "prompts" / "feedback_generator.txt"
SYSTEM_PROMPT = _PROMPT_PATH.read_text()


async def generate_feedback(
    topic_name: str,
    exam_name: str,
    today_tasks_summary: str,
    completed_count: int,
    total_count: int,
    pace_context: dict,
) -> FeedbackResponse:
    """
    Agent 7 — Generate mentor-style feedback.
    All pace numbers are pre-computed by backend and passed in — the AI interprets, not calculates.
    """
    user_msg = (
        f"STUDENT CONTEXT\n"
        f"Exam: {exam_name}\n"
        f"Module topic: {topic_name}\n\n"
        f"TODAY'S PERFORMANCE\n"
        f"Tasks completed: {completed_count}/{total_count}\n"
        f"Summary: {today_tasks_summary}\n\n"
        f"PACE METRICS (pre-computed — use these numbers, do not recalculate)\n"
        f"Days elapsed in module: {pace_context['days_elapsed']}/{pace_context['days_total']}\n"
        f"Hours delta (actual - planned so far): {pace_context['hours_delta']:+.1f}h\n"
        f"Today's completion fraction: {pace_context['today_completion_fraction']:.0%}\n"
        f"Topic completion: {pace_context['topic_completion_pct']:.1f}%\n"
        f"Overall exam completion: {pace_context['overall_exam_completion_pct']:.1f}%\n"
        f"Days remaining until exam: {pace_context.get('days_remaining_exam', 'not set')}\n"
        f"Current study streak: {pace_context['current_streak_days']} day(s)\n"
        f"Days remaining in module: {pace_context['days_remaining_in_module']}\n"
    )

    raw = await call_groq(SYSTEM_PROMPT, user_msg, model=HEAVY_MODEL)
    return await validate_with_retry(raw, FeedbackResponse, SYSTEM_PROMPT, user_msg, HEAVY_MODEL)

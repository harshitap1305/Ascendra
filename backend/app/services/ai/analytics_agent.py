"""
Agent 8 — Analytics Reviewer.
Generates narrative weekly/monthly reviews from pre-computed stats.
The AI never computes any number — all stats are injected from Python.
"""
from datetime import date
from pathlib import Path

from app.schemas.ai_analytics import AnalyticsReviewResponse
from app.services.ai.client import call_groq, HEAVY_MODEL
from app.utils.validation import validate_with_retry

_PROMPT_PATH = Path(__file__).parent / "prompts" / "analytics_agent.txt"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text()


async def generate_review(
    exam_name: str,
    period_type: str,         # "weekly" | "monthly"
    period_start: date,
    period_end: date,
    stats: dict,
) -> AnalyticsReviewResponse:
    """
    Given pre-computed stats, returns narrative review from Agent 8.
    Retries on schema validation failure (same pattern as all other agents).
    """
    user_msg = _build_user_message(exam_name, period_type, period_start, period_end, stats)

    async def _call(feedback: str | None = None) -> str:
        msg = user_msg
        if feedback:
            msg += f"\n\n[PREVIOUS RESPONSE WAS INVALID: {feedback}. Fix and re-output valid JSON.]"
        return await call_groq(system=_SYSTEM_PROMPT, user_message=msg, model=HEAVY_MODEL)

    return await validate_with_retry(_call, AnalyticsReviewResponse, max_retries=2)


def _build_user_message(
    exam_name: str,
    period_type: str,
    period_start: date,
    period_end: date,
    stats: dict,
) -> str:
    on_track_str = "yes" if stats.get("on_track") else ("no" if stats.get("on_track") is False else "unknown")
    topic_summary = "\n".join(
        f"  - {t['topic_name']}: {t['completion_pct']:.1f}% complete ({t['status']})"
        for t in stats.get("topic_breakdown", [])[:15]  # cap at 15 to avoid token bloat
    ) or "  No topic data available yet."

    return f"""EXAM: {exam_name}
PERIOD: {period_type.upper()} ({period_start} to {period_end})

=== STATS (computed from database — do NOT change these numbers) ===
Planned hours this period:    {stats.get('planned_hours', 0):.1f}h
Actual hours studied:         {stats.get('actual_hours', 0):.1f}h
Productivity rate:            {stats.get('avg_productivity_pct', 'N/A')}% (actual / planned)
Topics completed this period: {stats.get('topics_completed', 0)}
Active study days:            {stats.get('active_days', 0)}
Skipped/missed days:          {stats.get('skipped_days', 0)}
Weekly consistency:           {stats.get('consistency_pct', 'N/A')}%

=== CONTEXT ===
Overall exam completion:      {stats.get('exam_completion_pct', 0):.1f}%
Days until exam:              {stats.get('days_remaining_exam', 'Unknown')}
Projected finish date:        {stats.get('projected_finish_date', 'Unknown')}
Required daily hours to pass: {stats.get('required_daily_hours', 'N/A')} h/day
On track:                     {on_track_str}

=== TOPIC COMPLETION BREAKDOWN (source for strong/weak topics) ===
{topic_summary}

Write the review JSON now."""

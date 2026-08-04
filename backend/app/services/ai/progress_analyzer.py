import json
from pathlib import Path
from app.schemas.ai_progress import ProgressAnalysisResponse
from app.services.ai.client import call_groq, HEAVY_MODEL
from app.services.ai.validation import validate_with_retry

_PROMPT_PATH = Path(__file__).parent / "prompts" / "progress_analyzer.txt"
SYSTEM_PROMPT = _PROMPT_PATH.read_text()


async def analyze_progress(
    tasks: list[dict],
    raw_text: str,
) -> ProgressAnalysisResponse:
    """
    Agent 6 — Extract structured progress from the student's free-text check-in.
    Matches text against the planned task list using task_ref identifiers.
    """
    tasks_summary = "\n".join(
        f"[{t['task_ref']}] {t['description']} ({t['estimated_hours']}h, type={t['type']})"
        for t in tasks
    )
    user_msg = (
        f"Today's planned tasks:\n{tasks_summary}\n\n"
        f"Student's check-in:\n\"\"\"\n{raw_text}\n\"\"\""
    )
    raw = await call_groq(SYSTEM_PROMPT, user_msg, model=HEAVY_MODEL)
    return await validate_with_retry(raw, ProgressAnalysisResponse, SYSTEM_PROMPT, user_msg, HEAVY_MODEL)

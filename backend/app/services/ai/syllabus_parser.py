import json
from pathlib import Path
from pydantic import ValidationError

from app.schemas.ai_syllabus import ParsedSyllabusResponse
from app.services.ai.client import call_groq, HEAVY_MODEL

_PROMPT_PATH = Path(__file__).parent / "prompts" / "syllabus_parser.txt"
SYSTEM_PROMPT = _PROMPT_PATH.read_text()


async def parse_syllabus(exam_name: str, raw_text: str) -> ParsedSyllabusResponse:
    """
    Agent 1 — Convert raw pasted syllabus text into a structured topic tree.

    Two-layer retry strategy:
      Layer 1: tenacity inside call_groq() handles transient network/API errors.
      Layer 2: On Pydantic schema mismatch, feed the error back and retry once.
    """
    user_msg = (
        f"Exam: {exam_name}\n"
        f"Raw syllabus text:\n"
        f'"""\n{raw_text}\n"""'
    )

    raw = await call_groq(SYSTEM_PROMPT, user_msg, model=HEAVY_MODEL)

    try:
        data = json.loads(raw)
        return ParsedSyllabusResponse.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        # Feed the validation error back — AI sees what was wrong and corrects it
        retry_msg = (
            f"{user_msg}\n\n"
            f"Your previous response failed schema validation:\n{e}\n"
            f"Return ONLY corrected JSON matching the required schema exactly."
        )
        raw = await call_groq(SYSTEM_PROMPT, retry_msg, model=HEAVY_MODEL)
        data = json.loads(raw)
        return ParsedSyllabusResponse.model_validate(data)
        # Raises if it fails again — caller catches and marks upload as failed

from pathlib import Path
from app.schemas.ai_syllabus import ParsedSyllabusResponse
from app.services.ai.client import call_groq, HEAVY_MODEL
from app.services.ai.validation import validate_with_retry

_PROMPT_PATH = Path(__file__).parent / "prompts" / "syllabus_parser.txt"
SYSTEM_PROMPT = _PROMPT_PATH.read_text()


async def parse_syllabus(exam_name: str, raw_text: str) -> ParsedSyllabusResponse:
    """
    Agent 1 — Convert raw pasted syllabus text into a structured topic tree.
    """
    user_msg = (
        f"Exam: {exam_name}\n"
        f"Raw syllabus text:\n"
        f'"""\n{raw_text}\n"""'
    )
    raw = await call_groq(SYSTEM_PROMPT, user_msg, model=HEAVY_MODEL)
    return await validate_with_retry(raw, ParsedSyllabusResponse, SYSTEM_PROMPT, user_msg, HEAVY_MODEL)

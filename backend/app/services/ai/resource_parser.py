from pathlib import Path
from app.schemas.ai_resource_parser import ParsedResourcesResponse
from app.services.ai.client import call_groq, HEAVY_MODEL
from app.services.ai.validation import validate_with_retry

_PROMPT_PATH = Path(__file__).parent / "prompts" / "resource_parser.txt"
SYSTEM_PROMPT = _PROMPT_PATH.read_text()


async def parse_resources(raw_text: str, topic_name: str) -> ParsedResourcesResponse:
    """
    Agent 3 — Extract structured resources from the student's raw text dump.
    e.g. "watch Gate Smashers, read Galvin ch 1-5, 200 PYQs, ~20 hours"
    """
    user_msg = (
        f"Topic being studied: {topic_name}\n"
        f"Student's resource description:\n"
        f'"""\n{raw_text}\n"""'
    )
    raw = await call_groq(SYSTEM_PROMPT, user_msg, model=HEAVY_MODEL)
    return await validate_with_retry(raw, ParsedResourcesResponse, SYSTEM_PROMPT, user_msg, HEAVY_MODEL)

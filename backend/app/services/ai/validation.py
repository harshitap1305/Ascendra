"""
Shared validation helper for all AI agents.
Extracts the validate-and-retry pattern that was duplicated in every agent.
"""
import json
from pydantic import ValidationError
from app.services.ai.client import call_groq


async def validate_with_retry(
    raw_response: str,
    schema_cls,
    system_prompt: str,
    user_message: str,
    model: str,
):
    """
    Layer 2 retry: validates AI output against a Pydantic schema.
    If the JSON is valid but schema is wrong, feeds the error back to the AI once.
    Layer 1 (network/API errors) is handled inside call_groq() via tenacity.

    Raises ValidationError if still invalid after one retry.
    """
    try:
        return schema_cls.model_validate(json.loads(raw_response))
    except (json.JSONDecodeError, ValidationError) as e:
        retry_msg = (
            f"{user_message}\n\n"
            f"Your previous response failed schema validation:\n{e}\n"
            f"Return ONLY corrected JSON matching the required schema exactly."
        )
        raw_response = await call_groq(system_prompt, retry_msg, model=model)
        return schema_cls.model_validate(json.loads(raw_response))
        # Raises if still wrong — caller handles as a failed job

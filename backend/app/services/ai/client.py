"""
Thin wrapper around the Groq SDK.
- tenacity handles transient network/API errors (layer 1 retry)
- Callers handle Pydantic ValidationError (layer 2 retry with error feedback)
"""
from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings

_client = AsyncGroq(api_key=settings.GROQ_API_KEY)

# Model tiers — swap here for all agents at once if Groq releases better models
HEAVY_MODEL = "llama-3.3-70b-versatile"   # parsing, planning, feedback
LIGHT_MODEL = "llama-3.1-8b-instant"       # daily tasks, progress extraction


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def call_groq(
    system: str,
    user_message: str,
    model: str = HEAVY_MODEL,
    json_mode: bool = True,
) -> str:
    """
    Call Groq chat completions and return the raw response string.
    json_mode=True enforces JSON output at the API level (reduces parse failures).
    """
    response = await _client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"} if json_mode else None,
        max_tokens=4096,
        temperature=0.1,  # low temperature = more deterministic, better for JSON
    )
    return response.choices[0].message.content

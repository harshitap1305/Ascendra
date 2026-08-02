"""
Logging wrapper — call this around every AI service function so every call
is persisted to ai_interactions regardless of success or failure.
"""
import time
from typing import Any, Callable, Awaitable
from beanie import PydanticObjectId
from app.models.ai_interaction import AIInteraction


async def log_ai_call(
    agent_type: str,
    user_id: PydanticObjectId,
    exam_id: PydanticObjectId | None,
    input_payload: dict,
    model_used: str,
    fn: Callable[..., Awaitable[Any]],
    *args,
    **kwargs,
) -> Any:
    """
    Wraps an async AI service call, persists the result (or failure) to
    ai_interactions, and re-raises any exception after logging.
    """
    start = time.monotonic()
    status = "success"
    output_payload: dict | None = None

    try:
        result = await fn(*args, **kwargs)
        # Pydantic model → dict for storage; plain dicts pass through
        output_payload = (
            result.model_dump() if hasattr(result, "model_dump") else result
        )
        return result

    except Exception:
        status = "failed"
        raise

    finally:
        latency_ms = int((time.monotonic() - start) * 1000)
        try:
            await AIInteraction(
                user_id=user_id,
                exam_id=exam_id,
                agent_type=agent_type,
                input_payload=input_payload,
                output_payload=output_payload,
                model_used=model_used,
                latency_ms=latency_ms,
                status=status,
            ).insert()
        except Exception:
            # Never let logging failure hide the real error
            pass

"""Tests for the shared validate_with_retry helper."""
import pytest
import json
from unittest.mock import AsyncMock, patch
from pydantic import BaseModel, ValidationError


class SimpleSchema(BaseModel):
    value: int
    name: str


@pytest.mark.asyncio
async def test_validate_with_retry_success():
    """Valid JSON that matches schema passes first time."""
    from app.services.ai.validation import validate_with_retry
    raw = json.dumps({"value": 42, "name": "test"})
    result = await validate_with_retry(raw, SimpleSchema, "sys", "user", "test-model")
    assert result.value == 42
    assert result.name == "test"


@pytest.mark.asyncio
async def test_validate_with_retry_bad_json_triggers_retry():
    """Malformed JSON triggers one retry call to the AI."""
    from app.services.ai.validation import validate_with_retry
    corrected = json.dumps({"value": 99, "name": "corrected"})
    with patch("app.services.ai.validation.call_groq", new_callable=AsyncMock) as mock:
        mock.return_value = corrected
        result = await validate_with_retry("not json at all", SimpleSchema, "sys", "user", "test-model")
    mock.assert_called_once()
    assert result.value == 99


@pytest.mark.asyncio
async def test_validate_with_retry_schema_mismatch_triggers_retry():
    """Valid JSON but wrong schema fields triggers one retry."""
    from app.services.ai.validation import validate_with_retry
    wrong_schema = json.dumps({"wrong_field": "oops"})
    corrected = json.dumps({"value": 7, "name": "fixed"})
    with patch("app.services.ai.validation.call_groq", new_callable=AsyncMock) as mock:
        mock.return_value = corrected
        result = await validate_with_retry(wrong_schema, SimpleSchema, "sys", "user", "test-model")
    mock.assert_called_once()
    assert result.value == 7


@pytest.mark.asyncio
async def test_validate_with_retry_raises_if_retry_also_fails():
    """If retry also returns bad data, ValidationError propagates."""
    from app.services.ai.validation import validate_with_retry
    still_wrong = json.dumps({"wrong": "again"})
    with patch("app.services.ai.validation.call_groq", new_callable=AsyncMock) as mock:
        mock.return_value = still_wrong
        with pytest.raises(ValidationError):
            await validate_with_retry("bad", SimpleSchema, "sys", "user", "test-model")

"""Tests for the Resource Parser AI agent (Agent 3)."""
import pytest
import json
from unittest.mock import AsyncMock, patch
from app.schemas.ai_resource_parser import ParsedResourcesResponse


VALID_RESPONSE = json.dumps({
    "resources": [
        {"type": "video", "title": "Gate Smashers OS Playlist", "source_name": "Gate Smashers",
         "url": None, "total_units": 45},
        {"type": "book", "title": "Operating System Concepts", "source_name": "Galvin",
         "url": None, "total_units": None},
        {"type": "practice", "title": "GATE OS PYQs", "source_name": None,
         "url": None, "total_units": 200},
    ],
    "estimated_total_hours": 20.0,
})

INVALID_RESPONSE = json.dumps({"wrong_key": "bad"})


@pytest.mark.asyncio
async def test_resource_parser_happy_path():
    """Agent 3 extracts resources correctly from a valid AI response."""
    from app.services.ai.resource_parser import parse_resources
    with patch("app.services.ai.resource_parser.call_groq", new_callable=AsyncMock) as mock:
        mock.return_value = VALID_RESPONSE
        result = await parse_resources("I'll watch Gate Smashers and read Galvin", "Operating Systems")
    assert isinstance(result, ParsedResourcesResponse)
    assert len(result.resources) == 3
    assert result.resources[0].type == "video"
    assert result.resources[0].total_units == 45
    assert result.estimated_total_hours == 20.0


@pytest.mark.asyncio
async def test_resource_parser_empty_resources():
    """Agent 3 handles a response with no extractable resources gracefully."""
    from app.services.ai.resource_parser import parse_resources
    empty = json.dumps({"resources": [], "estimated_total_hours": None})
    with patch("app.services.ai.resource_parser.call_groq", new_callable=AsyncMock) as mock:
        mock.return_value = empty
        result = await parse_resources("I'm not sure what to use", "Topic")
    assert len(result.resources) == 0
    assert result.estimated_total_hours is None


@pytest.mark.asyncio
async def test_resource_parser_triggers_retry_on_bad_schema():
    """Bad schema triggers one retry call through the validation helper."""
    from app.services.ai.resource_parser import parse_resources
    call_count = 0

    async def mock_resource_parser_call(system, user, model=None, json_mode=None):
        nonlocal call_count
        call_count += 1
        return VALID_RESPONSE

    async def mock_validation_retry_call(system, user, model=None, json_mode=None):
        return VALID_RESPONSE

    # Patch: resource_parser calls call_groq once (returns bad), then validation calls it for retry
    with patch("app.services.ai.resource_parser.call_groq", new_callable=AsyncMock, return_value=INVALID_RESPONSE):
        with patch("app.services.ai.validation.call_groq", new_callable=AsyncMock, return_value=VALID_RESPONSE):
            result = await parse_resources("raw text", "Topic")
    assert len(result.resources) == 3


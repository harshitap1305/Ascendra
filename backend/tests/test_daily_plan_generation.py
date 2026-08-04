"""
Tests for Agent 5 (Daily Planner) schema and Agent 6 (Progress Analyzer) schema.
All AI calls are mocked — no real API keys needed.
"""
import pytest
import json
from unittest.mock import AsyncMock, patch
from app.schemas.ai_daily_planner import DailyPlanResponse, DailyTask
from app.schemas.ai_progress import ProgressAnalysisResponse, TaskResult
from app.schemas.ai_feedback import FeedbackResponse


# ── DailyPlanResponse schema validation ──────────────────────────────────────

def test_daily_plan_schema_valid():
    data = {
        "tasks": [
            {
                "task_ref": "t1",
                "description": "Watch Gate Smashers Ep 4-6",
                "type": "study",
                "estimated_hours": 1.5,
                "topic_name": "Processes",
                "resource_detail": "Gate Smashers OS Playlist"
            }
        ],
        "planned_hours": 1.5,
        "daily_goal": "Understand process scheduling fundamentals",
        "carry_over_note": None
    }
    plan = DailyPlanResponse(**data)
    assert len(plan.tasks) == 1
    assert plan.tasks[0].task_ref == "t1"
    assert plan.planned_hours == 1.5


def test_daily_task_invalid_type_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="type must be one of"):
        DailyTask(
            task_ref="t1",
            description="Watch something",
            type="unknown_type",
            estimated_hours=1.0,
            topic_name="OS",
        )


def test_daily_plan_empty_tasks_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="tasks list cannot be empty"):
        DailyPlanResponse(tasks=[], planned_hours=0.0, daily_goal="test")


def test_daily_task_zero_hours_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="estimated_hours must be > 0"):
        DailyTask(
            task_ref="t1",
            description="Read",
            type="study",
            estimated_hours=0.0,
            topic_name="OS",
        )


# ── ProgressAnalysisResponse schema validation ────────────────────────────────

def test_progress_schema_valid():
    data = {
        "task_results": [
            {"task_ref": "t1", "status": "completed", "units_completed": 3},
            {"task_ref": "t2", "status": "partial", "units_completed": 15},
        ],
        "actual_hours_spent": 2.5,
        "confidence_rating": 4,
        "mood_note": "felt good",
        "delay_reason": None,
        "overall_completion_today": 0.75
    }
    result = ProgressAnalysisResponse(**data)
    assert result.confidence_rating == 4
    assert result.overall_completion_today == 0.75


def test_progress_status_not_mentioned_valid():
    data = {
        "task_results": [
            {"task_ref": "t1", "status": "not_mentioned"},
        ],
        "overall_completion_today": 0.0
    }
    result = ProgressAnalysisResponse(**data)
    assert result.task_results[0].status == "not_mentioned"


def test_progress_invalid_status_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="status must be one of"):
        TaskResult(task_ref="t1", status="wrong_status")


def test_progress_confidence_out_of_range_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ProgressAnalysisResponse(
            task_results=[{"task_ref": "t1", "status": "completed"}],
            confidence_rating=6,  # > 5
            overall_completion_today=1.0
        )


def test_progress_completion_clamped_to_range():
    """overall_completion_today > 1.0 is clamped to 1.0."""
    result = ProgressAnalysisResponse(
        task_results=[{"task_ref": "t1", "status": "completed"}],
        overall_completion_today=1.5,  # exceeds 1.0
    )
    assert result.overall_completion_today == 1.0


# ── FeedbackResponse schema validation ───────────────────────────────────────

def test_feedback_schema_valid():
    data = {
        "performance_summary": "You completed 3/4 tasks today.",
        "pace_status": "on_track",
        "risk_level": "low",
        "suggestions": ["Focus on Deadlock tomorrow", "Start PYQs 30 mins earlier"],
        "motivational_note": "Solid day — keep the momentum going.",
    }
    fb = FeedbackResponse(**data)
    assert fb.pace_status == "on_track"
    assert len(fb.suggestions) == 2


def test_feedback_invalid_pace_status_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="pace_status must be one of"):
        FeedbackResponse(
            performance_summary="Done",
            pace_status="slightly_behind",  # invalid
            risk_level="medium",
            suggestions=["Try harder"],
            motivational_note="...",
        )


def test_feedback_empty_suggestions_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="suggestions must have at least one item"):
        FeedbackResponse(
            performance_summary="Done",
            pace_status="on_track",
            risk_level="low",
            suggestions=[],  # empty
            motivational_note="...",
        )


def test_feedback_suggestions_capped_at_five():
    """More than 5 suggestions are silently truncated."""
    data = {
        "performance_summary": "Done",
        "pace_status": "on_track",
        "risk_level": "low",
        "suggestions": [f"tip {i}" for i in range(8)],
        "motivational_note": "...",
    }
    fb = FeedbackResponse(**data)
    assert len(fb.suggestions) == 5


# ── Agent 5 (Daily Planner) happy path — mocked ──────────────────────────────

@pytest.mark.asyncio
async def test_daily_planner_agent_happy_path():
    """Agent 5 returns a valid DailyPlanResponse from a mocked AI call."""
    from app.services.ai.daily_planner import generate_daily_plan
    mock_response = json.dumps({
        "tasks": [
            {
                "task_ref": "t1",
                "description": "Watch Gate Smashers OS Ep 1-3 (Intro to Processes)",
                "type": "study",
                "estimated_hours": 1.0,
                "topic_name": "Processes",
                "resource_detail": "Gate Smashers OS Playlist"
            },
            {
                "task_ref": "t2",
                "description": "Solve 20 GATE PYQs on Processes",
                "type": "practice",
                "estimated_hours": 1.5,
                "topic_name": "Processes",
                "resource_detail": None
            }
        ],
        "planned_hours": 2.5,
        "daily_goal": "Build a solid foundation on Processes",
        "carry_over_note": None
    })
    with patch("app.services.ai.daily_planner.call_groq", new_callable=AsyncMock, return_value=mock_response):
        result = await generate_daily_plan(
            topic_name="Operating Systems",
            day_number=1,
            total_days=10,
            focus_topics=["Processes", "PCB"],
            planned_hours=3.0,
            planned_resources=[{"type": "video", "detail": "Gate Smashers Ep 1-3"}],
            goals="Understand process fundamentals",
            daily_hours_available=4.0,
            carry_over_tasks=[],
        )
    assert len(result.tasks) == 2
    assert result.tasks[0].task_ref == "t1"
    assert result.planned_hours == 2.5


# ── Agent 6 (Progress Analyzer) happy path — mocked ──────────────────────────

@pytest.mark.asyncio
async def test_progress_analyzer_agent_happy_path():
    """Agent 6 returns a valid ProgressAnalysisResponse from a mocked AI call."""
    from app.services.ai.progress_analyzer import analyze_progress
    mock_response = json.dumps({
        "task_results": [
            {"task_ref": "t1", "status": "completed", "units_completed": 3},
            {"task_ref": "t2", "status": "partial", "units_completed": 18},
        ],
        "actual_hours_spent": 2.0,
        "confidence_rating": 4,
        "mood_note": "felt good",
        "delay_reason": None,
        "overall_completion_today": 0.7
    })
    tasks = [
        {"task_ref": "t1", "description": "Watch 3 videos", "estimated_hours": 1.0, "type": "study"},
        {"task_ref": "t2", "description": "Solve 30 PYQs", "estimated_hours": 1.5, "type": "practice"},
    ]
    with patch("app.services.ai.progress_analyzer.call_groq", new_callable=AsyncMock, return_value=mock_response):
        result = await analyze_progress(tasks, "watched all videos, solved 18 questions")
    assert result.task_results[0].status == "completed"
    assert result.task_results[1].status == "partial"
    assert result.task_results[1].units_completed == 18
    assert result.confidence_rating == 4
    assert result.overall_completion_today == 0.7

"""Tests for the Planner AI agent (Agent 4) and plan constraint validation."""
import pytest
import json
from unittest.mock import AsyncMock, patch
from app.services.ai.planner import PlannerContext, _validate_plan_constraints, PlanConstraintError
from app.schemas.ai_planner import MasterPlanResponse, PlanDay


def make_context(days_remaining=30, daily_hours=4.0):
    return PlannerContext(
        exam_name="GATE CS 2027",
        experience_level="intermediate",
        overall_completion_pct=25.0,
        topic_name="Operating Systems",
        subtopics=[{"name": "Processes", "difficulty": "medium", "estimated_hours": 4, "status": "not_started"}],
        raw_module_input_text="Watch Gate Smashers, read Galvin, 200 PYQs",
        module_resources=[{"type": "video", "title": "Gate Smashers OS", "total_units": 45}],
        daily_hours_available=daily_hours,
        days_remaining=days_remaining,
    )


def make_plan(total_days=10, planned_hours_per_day=4.0):
    return MasterPlanResponse(
        total_days=total_days,
        summary="A 10-day OS study plan",
        days=[
            PlanDay(
                day_number=i + 1,
                focus_topics=["Processes"],
                planned_hours=planned_hours_per_day,
                goals=f"Goal for day {i+1}",
            )
            for i in range(total_days)
        ],
    )


def test_plan_constraints_valid():
    """A well-formed plan within all constraints passes without error."""
    ctx = make_context(days_remaining=15, daily_hours=4.0)
    plan = make_plan(total_days=10, planned_hours_per_day=4.0)
    _validate_plan_constraints(plan, ctx)  # should not raise


def test_plan_constraints_exceeds_days_remaining():
    """Plan spanning more days than exam deadline must raise PlanConstraintError."""
    ctx = make_context(days_remaining=5, daily_hours=4.0)
    plan = make_plan(total_days=10)
    with pytest.raises(PlanConstraintError, match="only 5 days remain"):
        _validate_plan_constraints(plan, ctx)


def test_plan_constraints_exceeds_daily_hours_budget():
    """Any day exceeding 110% of daily budget raises PlanConstraintError."""
    ctx = make_context(days_remaining=30, daily_hours=4.0)
    plan = make_plan(total_days=5, planned_hours_per_day=5.0)  # 5.0 > 4.0 * 1.1 = 4.4
    with pytest.raises(PlanConstraintError, match="exceeding the 4.0h daily budget"):
        _validate_plan_constraints(plan, ctx)


def test_plan_constraints_within_10pct_buffer_allowed():
    """Daily hours at exactly 10% over budget (4.4h when budget is 4h) is allowed."""
    ctx = make_context(days_remaining=30, daily_hours=4.0)
    plan = make_plan(total_days=5, planned_hours_per_day=4.4)  # 4.4 == 4.0 * 1.1, boundary
    _validate_plan_constraints(plan, ctx)  # should not raise


def test_plan_constraints_no_days_remaining_skips_check():
    """If days_remaining is None (no exam date set), day count constraint is skipped."""
    ctx = make_context(days_remaining=None, daily_hours=4.0)
    plan = make_plan(total_days=100)  # Very long plan
    _validate_plan_constraints(plan, ctx)  # should not raise


@pytest.mark.asyncio
async def test_planner_happy_path():
    """Planner returns a validated plan from a well-formed AI response."""
    from app.services.ai.planner import generate_plan
    valid_plan_json = json.dumps({
        "total_days": 10,
        "summary": "A 10-day OS plan",
        "days": [
            {
                "day_number": i + 1,
                "focus_topics": ["Processes"],
                "planned_hours": 3.5,
                "resources_to_cover": [],
                "goals": f"Finish day {i+1}",
            }
            for i in range(10)
        ],
    })
    ctx = make_context(days_remaining=15, daily_hours=4.0)
    with patch("app.services.ai.planner.call_groq", new_callable=AsyncMock) as mock:
        mock.return_value = valid_plan_json
        result = await generate_plan(ctx)
    assert result.total_days == 10
    assert len(result.days) == 10

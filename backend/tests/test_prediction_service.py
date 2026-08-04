"""
Table-driven unit tests for Module 4 completion projection calculations.
Tests pace calculations, required daily hours, and on-track status without requiring DB access.
"""
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from beanie import PydanticObjectId
from app.services import prediction_service

SCENARIOS = [
    {
        "name": "standard pace on track",
        "total_hours": 100.0,
        "completed_hours": 20.0,  # remaining 80
        "avg_daily_hours": 2.0,   # needs 40 days
        "days_remaining_exam": 50,
        "expect_required_daily": 1.6,  # 80 / 50
        "expect_on_track": True,
        "expect_days_needed": 40,
    },
    {
        "name": "behind pace",
        "total_hours": 150.0,
        "completed_hours": 30.0,  # remaining 120
        "avg_daily_hours": 1.5,   # needs 80 days
        "days_remaining_exam": 30,
        "expect_required_daily": 4.0,  # 120 / 30
        "expect_on_track": False,
        "expect_days_needed": 80,
    },
    {
        "name": "no data yet (zero avg daily hours)",
        "total_hours": 100.0,
        "completed_hours": 10.0,
        "avg_daily_hours": None,  # e.g., <3 study days logged
        "days_remaining_exam": 45,
        "expect_required_daily": 2.0,  # 90 / 45
        "expect_on_track": None,
        "expect_days_needed": None,
    },
    {
        "name": "exam already passed or today",
        "total_hours": 100.0,
        "completed_hours": 50.0,
        "avg_daily_hours": 2.0,
        "days_remaining_exam": -5,
        "expect_required_daily": None,
        "expect_on_track": False,
        "expect_days_needed": 25,
    },
    {
        "name": "all topics already completed",
        "total_hours": 100.0,
        "completed_hours": 100.0,  # remaining 0
        "avg_daily_hours": 2.0,
        "days_remaining_exam": 20,
        "expect_required_daily": None,
        "expect_on_track": True,
        "expect_days_needed": 0,
    },
]


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
async def test_project_completion_table_driven(scenario):
    exam_id = PydanticObjectId("507f1f77bcf86cd799439011")
    today = date.today()
    exam = MagicMock()
    exam.exam_date = today + timedelta(days=scenario["days_remaining_exam"])

    mock_aggregate = MagicMock()
    mock_aggregate.to_list = AsyncMock(return_value=[{
        "total_hours": scenario["total_hours"],
        "completed_hours": scenario["completed_hours"],
    }])

    with patch("app.models.exam.Exam.get", AsyncMock(return_value=exam)), \
         patch("app.models.topic.Topic.aggregate", return_value=mock_aggregate), \
         patch("app.services.prediction_service._compute_rolling_avg_daily_hours", AsyncMock(return_value=scenario["avg_daily_hours"])):
        
        result = await prediction_service.project_completion(exam_id)
        
        assert result.days_remaining == scenario["days_remaining_exam"]
        assert result.required_daily_hours == scenario["expect_required_daily"]
        assert result.on_track == scenario["expect_on_track"]
        
        if scenario["expect_days_needed"] is not None:
            expected_date = today + timedelta(days=scenario["expect_days_needed"])
            assert result.projected_finish_date == expected_date
        else:
            assert result.projected_finish_date is None


@pytest.mark.asyncio
async def test_project_completion_exam_not_found():
    """Return empty/none fields gracefully if exam doesn't exist."""
    with patch("app.models.exam.Exam.get", AsyncMock(return_value=None)):
        res = await prediction_service.project_completion(PydanticObjectId("507f1f77bcf86cd799439011"))
        assert res.exam_date is None
        assert res.projected_finish_date is None
        assert res.on_track is None

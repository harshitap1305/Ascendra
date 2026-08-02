import pytest
from datetime import date
from pydantic import ValidationError
from app.schemas.exam import ExamCreate, ExamUpdate


def test_exam_create_valid():
    data = {
        "name": "GATE CS 2027",
        "description": "Preparation for computer science GATE exam",
        "daily_study_hours": 5.0,
        "experience_level": "intermediate",
        "goal_score": "AIR under 500",
    }
    exam = ExamCreate(**data)
    assert exam.name == "GATE CS 2027"
    assert exam.daily_study_hours == 5.0
    assert exam.experience_level == "intermediate"


def test_exam_create_invalid_hours():
    with pytest.raises(ValidationError) as exc:
        ExamCreate(name="Test Exam", daily_study_hours=25.0)
    assert "daily_study_hours must be between 0 and 24" in str(exc.value)

    with pytest.raises(ValidationError):
        ExamCreate(name="Test Exam", daily_study_hours=0)


def test_exam_create_invalid_experience_level():
    with pytest.raises(ValidationError) as exc:
        ExamCreate(name="Test Exam", experience_level="pro")
    assert "experience_level must be one of" in str(exc.value)


def test_exam_update_partial():
    update = ExamUpdate(daily_study_hours=6.5)
    dump = update.model_dump(exclude_unset=True)
    assert dump == {"daily_study_hours": 6.5}
    assert "name" not in dump

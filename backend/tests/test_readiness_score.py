"""
Tests for the Exam Readiness Score calculation in Module 4.
Pure unit tests — no database, AI, or external network needed.
"""
import pytest
from app.services.prediction_service import compute_readiness_score, READINESS_WEIGHTS


def test_readiness_perfect_score():
    score, breakdown = compute_readiness_score(
        completion_pct=100.0,
        consistency_score=100.0,
        pace_on_track=True,
        days_remaining=30,
        avg_confidence=5.0,
    )
    assert score == 100
    assert breakdown["completion"] == 40
    assert breakdown["consistency"] == 25
    assert breakdown["pace"] == 20
    assert breakdown["confidence"] == 15


def test_readiness_zero_inputs_with_urgent_pace():
    # When pace is behind and days_remaining < 14, pace_score is 15.
    # When avg_confidence is None, default confidence_score is 60.
    # Expected: 0 + 0 + 15 * 0.20 + 60 * 0.15 = 3 + 9 = 12
    score, breakdown = compute_readiness_score(
        completion_pct=0.0,
        consistency_score=0.0,
        pace_on_track=False,
        days_remaining=10,
        avg_confidence=None,
    )
    assert score == 12
    assert breakdown["completion"] == 0
    assert breakdown["consistency"] == 0
    assert breakdown["pace"] == 3
    assert breakdown["confidence"] == 9


def test_readiness_behind_pace_moderate():
    # 60% completion, 80% consistency, behind pace with 45 days left (pace_score=40), confidence=3.0 (score=60)
    # Expected: 60*0.4 + 80*0.25 + 40*0.20 + 60*0.15 = 24 + 20 + 8 + 9 = 61
    score, breakdown = compute_readiness_score(
        completion_pct=60.0,
        consistency_score=80.0,
        pace_on_track=False,
        days_remaining=45,
        avg_confidence=3.0,
    )
    assert score == 61
    assert 45 < score < 75
    assert breakdown["weights"] == {
        "completion": "40%",
        "consistency": "25%",
        "pace": "20%",
        "confidence": "15%",
    }


def test_readiness_pace_urgency_scaling():
    # Verify that closer exam dates reduce readiness score more when behind pace
    score_far, _ = compute_readiness_score(50, 50, False, 60, 4.0)
    score_medium, _ = compute_readiness_score(50, 50, False, 20, 4.0)
    score_urgent, _ = compute_readiness_score(50, 50, False, 5, 4.0)
    
    assert score_far > score_medium > score_urgent


def test_readiness_weights_sum_to_one():
    total_weight = sum(READINESS_WEIGHTS.values())
    assert abs(total_weight - 1.0) < 1e-6

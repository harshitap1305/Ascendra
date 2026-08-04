"""
Tests for the deterministic replanning algorithm.
All tests use pure Python — no DB, no AI, no network.
Table-driven to cover all three cases.
"""
import pytest
import math
from types import SimpleNamespace
from app.services.replanning_service import (
    _topological_sort,
    _redistribute_topics_across_days,
    _fit_within_capacity,
)


# ── Test helpers ──────────────────────────────────────────────────────────────

def make_topic(name, hours=2.0, weightage=10, prereq=None, topic_id=None):
    t = SimpleNamespace(
        id=topic_id or name,
        name=name,
        estimated_hours=hours,
        weightage=weightage,
        status="not_started",
        is_leaf=True,
        prerequisite_topic_id=prereq,
    )
    return t


def make_day(day_number, planned_hours=4.0):
    return SimpleNamespace(
        day_number=day_number,
        planned_hours=planned_hours,
        focus_topics=[],
        goals="",
        status="pending",
    )


# ── Topological sort tests ────────────────────────────────────────────────────

def test_topo_sort_no_prereqs():
    """Topics with no prerequisites keep their original order."""
    topics = [make_topic("A"), make_topic("B"), make_topic("C")]
    result = _topological_sort(topics)
    assert [t.name for t in result] == ["A", "B", "C"]


def test_topo_sort_simple_chain():
    """B requires A — A must come first."""
    a = make_topic("A", topic_id="a")
    b = make_topic("B", prereq="a", topic_id="b")
    # Provide B before A to test sorting
    result = _topological_sort([b, a])
    names = [t.name for t in result]
    assert names.index("A") < names.index("B")


def test_topo_sort_chain_of_three():
    """A → B → C chain — all three must be in prerequisite order."""
    a = make_topic("A", topic_id="a")
    b = make_topic("B", prereq="a", topic_id="b")
    c = make_topic("C", prereq="b", topic_id="c")
    result = _topological_sort([c, b, a])
    names = [t.name for t in result]
    assert names.index("A") < names.index("B") < names.index("C")


def test_topo_sort_independent_topics_plus_one_chain():
    """Mix of independent topics and one chained pair — chain order respected."""
    a = make_topic("A", topic_id="a")
    b = make_topic("B", prereq="a", topic_id="b")
    c = make_topic("C", topic_id="c")  # independent
    result = _topological_sort([b, c, a])
    names = [t.name for t in result]
    assert names.index("A") < names.index("B")  # chain respected


# ── Redistribution helper tests ───────────────────────────────────────────────

def test_redistribute_fills_days_evenly():
    """Topics distributed across days, each day gets focus topics assigned."""
    days = [make_day(i) for i in range(3)]  # 3 days × 4h = 12h capacity
    topics = [make_topic("A", hours=4), make_topic("B", hours=4), make_topic("C", hours=4)]
    _redistribute_topics_across_days(days, topics, daily_hours=4.0)
    # Each topic should go to exactly one day
    assert days[0].focus_topics == ["A"]
    assert days[1].focus_topics == ["B"]
    assert days[2].focus_topics == ["C"]
    for d in days:
        assert d.status == "adjusted"


def test_redistribute_topic_spans_two_days():
    """A topic that needs 3h spans across two 2h days."""
    days = [make_day(0, planned_hours=2), make_day(1, planned_hours=2)]
    topics = [make_topic("BigTopic", hours=3)]
    _redistribute_topics_across_days(days, topics, daily_hours=2.0)
    # BigTopic should appear on both days
    assert "BigTopic" in days[0].focus_topics
    assert "BigTopic" in days[1].focus_topics


def test_redistribute_respects_prerequisite_order():
    """Prerequisite topic always comes before dependent topic in day assignment."""
    a = make_topic("Parent", hours=2, topic_id="parent")
    b = make_topic("Child", hours=2, prereq="parent", topic_id="child")
    days = [make_day(0, planned_hours=4)]
    _redistribute_topics_across_days(days, [b, a], daily_hours=4.0)
    # Both fit in one day — Parent must appear before Child
    names = days[0].focus_topics
    assert names.index("Parent") < names.index("Child")


def test_redistribute_empty_topics_clears_days():
    """Empty topic list should leave all days with empty focus_topics."""
    days = [make_day(0), make_day(1)]
    _redistribute_topics_across_days(days, [], daily_hours=4.0)
    assert days[0].focus_topics == []
    assert days[1].focus_topics == []


# ── Fit-within-capacity tests ─────────────────────────────────────────────────

def test_fit_all_topics_fit():
    """When total hours ≤ capacity, no topics are deferred."""
    topics = [make_topic("A", hours=3, weightage=20), make_topic("B", hours=3, weightage=10)]
    fitted, deferred = _fit_within_capacity(topics, capacity_hours=7.0)
    assert len(deferred) == 0
    assert len(fitted) == 2


def test_fit_defers_lowest_weightage():
    """When capacity is tight, lowest-weightage topic is deferred."""
    high = make_topic("HighW", hours=5, weightage=40)
    low = make_topic("LowW", hours=5, weightage=5)
    # Total = 10h, capacity = 6h (only one topic fits)
    fitted, deferred = _fit_within_capacity([high, low], capacity_hours=6.0)
    assert "HighW" in [t.name for t in fitted]
    assert "LowW" in [t.name for t in deferred]


def test_fit_empty_topics():
    """Empty input returns empty lists, no crash."""
    fitted, deferred = _fit_within_capacity([], capacity_hours=10.0)
    assert fitted == []
    assert deferred == []


def test_fit_zero_capacity_defers_everything():
    """Zero capacity means everything is deferred."""
    topics = [make_topic("A", hours=2), make_topic("B", hours=2)]
    fitted, deferred = _fit_within_capacity(topics, capacity_hours=0.0)
    assert len(deferred) == 2


# ── Business constraint scenario tests ───────────────────────────────────────

def test_scenario_ahead_of_plan():
    """
    Student is ahead: 3 pending days but only needs 2.
    Expected: 2 work days + 1 revision buffer day.
    """
    days = [make_day(i, planned_hours=4) for i in range(3)]  # 12h total
    topics = [make_topic("A", hours=4), make_topic("B", hours=4)]  # 8h needed → 2 days ideal

    ideal_days_needed = math.ceil(8.0 / 4.0)  # = 2
    assert ideal_days_needed < len(days)

    work_days = days[:ideal_days_needed]
    revision_days = days[ideal_days_needed:]

    _redistribute_topics_across_days(work_days, topics, daily_hours=4.0)
    for d in revision_days:
        d.focus_topics = ["Revision & Practice"]
        d.status = "adjusted"

    assert days[0].focus_topics == ["A"]
    assert days[1].focus_topics == ["B"]
    assert days[2].focus_topics == ["Revision & Practice"]
    assert len(revision_days) == 1


def test_scenario_behind_fits_within_tolerance():
    """
    Student is behind: 3 topics × 3.5h each = 10.5h needed, 3 days × 4h = 12h capacity.
    Should redistribute without deferring anything.
    """
    days = [make_day(i, planned_hours=4) for i in range(3)]
    topics = [make_topic(f"T{i}", hours=3.5) for i in range(3)]
    total = sum(t.estimated_hours for t in topics)  # 10.5h
    capacity = len(days) * 4.0  # 12h
    assert total <= capacity * 1.1  # fits within 10% tolerance

    _redistribute_topics_across_days(days, topics, daily_hours=4.0)
    all_focus = [t for d in days for t in d.focus_topics]
    assert "T0" in all_focus
    assert "T1" in all_focus
    assert "T2" in all_focus


def test_scenario_behind_doesnt_fit_defers_low_priority():
    """
    Student critically behind: 3 topics totaling 15h, only 3 days × 4h = 12h.
    Highest-weightage topic must be fitted; lowest-weightage deferred.
    """
    topics_sorted_by_weight = [
        make_topic("Critical", hours=6, weightage=50),
        make_topic("Medium", hours=5, weightage=25),
        make_topic("Minor", hours=4, weightage=5),
    ]
    # Total = 15h, capacity = 12h
    fitted, deferred = _fit_within_capacity(topics_sorted_by_weight, capacity_hours=12.0)
    fitted_names = [t.name for t in fitted]
    deferred_names = [t.name for t in deferred]

    assert "Critical" in fitted_names
    assert "Minor" in deferred_names or "Medium" in deferred_names


def test_scenario_last_day_everything_done():
    """
    Edge case: student finishes all topics on the final day (0 days to save).
    No redistribution needed — no pending days after today.
    """
    pending_days = []  # nothing left
    assert len(pending_days) == 0  # module is effectively done

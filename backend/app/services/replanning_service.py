"""
Deterministic replanning service — Module 3's most critical business logic.

Design principles:
- This is pure Python, NOT an AI call.
- Runs after EVERY check-in (not gated by feedback flag).
- NEVER silently pushes the module past the exam-date constraint.
- Respects prerequisite ordering from Module 1's topic graph.
- Greedy bin-packing: simple and predictable, not optimal.
"""
import math
from datetime import datetime, timezone
from typing import Optional
from beanie import PydanticObjectId

from app.models.topic import Topic
from app.models.module_plan_day import ModulePlanDay
from app.models.module_start import ModuleStart


# ── Topological Sort ──────────────────────────────────────────────────────────

def _topological_sort(topics: list[Topic]) -> list[Topic]:
    """
    Return topics in an order that respects prerequisite_topic_id chains.
    If topic B requires topic A, A comes first.
    Simple DFS — topic counts are small (≤ 20 typically).
    """
    id_map = {str(t.id): t for t in topics}
    visited: set[str] = set()
    result: list[Topic] = []

    def dfs(topic: Topic) -> None:
        if str(topic.id) in visited:
            return
        # Visit prerequisite first if it's in our set
        if topic.prerequisite_topic_id:
            prereq_id = str(topic.prerequisite_topic_id)
            if prereq_id in id_map and prereq_id not in visited:
                dfs(id_map[prereq_id])
        visited.add(str(topic.id))
        result.append(topic)

    for t in topics:
        dfs(t)
    return result


# ── Greedy Bin-Packing ────────────────────────────────────────────────────────

def _redistribute_topics_across_days(
    pending_days: list[ModulePlanDay],
    topics: list[Topic],
    daily_hours: float,
) -> None:
    """
    Distribute topics across days using greedy bin-packing.
    Respects prerequisite order. Mutates pending_days in place.
    """
    ordered = _topological_sort(topics)

    # Reset focus_topics on all days
    for d in pending_days:
        d.focus_topics = []

    if not pending_days:
        return

    day_idx = 0
    remaining_cap = pending_days[0].planned_hours or daily_hours

    for topic in ordered:
        hours_needed = topic.estimated_hours or 1.0
        while hours_needed > 0.05 and day_idx < len(pending_days):
            allocate = min(hours_needed, remaining_cap)
            pending_days[day_idx].focus_topics.append(topic.name)
            hours_needed -= allocate
            remaining_cap -= allocate
            if remaining_cap <= 0.1:
                day_idx += 1
                if day_idx < len(pending_days):
                    remaining_cap = pending_days[day_idx].planned_hours or daily_hours

    # Mark all touched days as adjusted
    for d in pending_days:
        d.status = "adjusted"


def _fit_within_capacity(
    topics: list[Topic],
    capacity_hours: float,
) -> tuple[list[Topic], list[Topic]]:
    """
    Greedy fit: take topics (sorted by weightage DESC) until capacity is full.
    Returns (fitted, deferred).
    """
    fitted = []
    deferred = []
    remaining = capacity_hours
    for t in topics:
        hours = t.estimated_hours or 1.0
        if hours <= remaining + 0.5:  # 0.5h grace
            fitted.append(t)
            remaining -= hours
        else:
            deferred.append(t)
    return fitted, deferred


# ── Main Pipeline ─────────────────────────────────────────────────────────────

async def redistribute(
    module_start_id: PydanticObjectId,
    today_completion_fraction: float,
) -> tuple[bool, Optional[str]]:
    """
    Runs deterministically after every check-in.
    Returns (plan_adjusted: bool, adjustment_summary: str | None).

    Logic:
    - Fetch incomplete leaf topics for this module
    - Fetch remaining pending module_plan_days
    - Compare workload vs capacity
    - Case 1 (ahead): compress pending days, add revision buffer
    - Case 2 (behind, fits): redistribute across existing days
    - Case 3 (behind, doesn't fit): prioritize by weightage, surface conflict
    """
    module_start = await ModuleStart.get(module_start_id)
    if not module_start:
        return False, None

    # Fetch all pending days sorted by day_number
    pending_days = await ModulePlanDay.find(
        {
            "module_plan_id": {"$exists": True},
            "status": "pending",
        }
    ).sort("day_number").to_list()

    # Filter to this module's plan
    from app.models.module_plan import ModulePlan
    plan = await ModulePlan.find_one(ModulePlan.module_start_id == module_start_id)
    if not plan:
        return False, None

    pending_days = [d for d in pending_days if d.module_plan_id == plan.id]

    if not pending_days:
        return False, None  # Nothing to replan — module days all done

    # Fetch incomplete leaf topics for this module's topic
    incomplete_topics = await _get_incomplete_topics_for_module(module_start)
    if not incomplete_topics:
        return False, None  # All topics done — no replanning needed

    daily_hours = module_start.daily_hours_available
    total_remaining_hours = sum(t.estimated_hours or 1.0 for t in incomplete_topics)
    available_capacity = len(pending_days) * daily_hours
    ideal_days_needed = math.ceil(total_remaining_hours / daily_hours)

    # ── Case 1: Ahead — work finished faster than planned ──
    if today_completion_fraction >= 0.9 and ideal_days_needed < len(pending_days):
        days_saved = len(pending_days) - ideal_days_needed
        work_days = pending_days[:ideal_days_needed]
        revision_days = pending_days[ideal_days_needed:]

        _redistribute_topics_across_days(work_days, incomplete_topics, daily_hours)

        # Freed days → revision buffer
        for d in revision_days:
            d.focus_topics = ["Revision & Practice"]
            d.goals = "Review and consolidate completed topics. Solve additional PYQs."
            d.status = "adjusted"
            await d.save()

        for d in work_days:
            await d.save()

        return True, f"Compressed module by {days_saved} day(s). Gained {days_saved} revision day(s) at the end."

    # ── Case 2: Behind but fits within tolerance ──
    if total_remaining_hours <= available_capacity * 1.1:
        _redistribute_topics_across_days(pending_days, incomplete_topics, daily_hours)
        for d in pending_days:
            await d.save()
        return True, "Remaining topics redistributed across existing days — you're still on track."

    # ── Case 3: Behind and doesn't fit — prioritize by weightage ──
    sorted_topics = sorted(incomplete_topics, key=lambda t: t.weightage or 0, reverse=True)
    fitted, deferred = _fit_within_capacity(sorted_topics, available_capacity)

    if fitted:
        _redistribute_topics_across_days(pending_days, fitted, daily_hours)
        for d in pending_days:
            await d.save()

    deferred_names = [t.name for t in deferred]
    hours_over = round(total_remaining_hours - available_capacity, 1)
    summary = (
        f"Workload exceeds remaining time by {hours_over}h. "
        f"Prioritized higher-weightage topics. "
        f"At-risk topics (consider increasing daily hours or splitting module): "
        f"{', '.join(deferred_names)}."
    ) if deferred else "Redistributed topics — workload tight but manageable."

    return True, summary


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_incomplete_topics_for_module(module_start: ModuleStart) -> list[Topic]:
    """
    Fetch leaf topics under this module's root topic that are not yet completed.
    These are the actual units of work that need to be redistributed.
    """
    # Get all descendants of the module's root topic
    descendants = await Topic.find({"ancestors": module_start.topic_id}).to_list()
    root_topic = await Topic.get(module_start.topic_id)

    all_topics = descendants
    if root_topic:
        all_topics = [root_topic] + descendants

    # Return only incomplete leaf topics (the actual work units)
    return [
        t for t in all_topics
        if t.is_leaf and t.status not in ("completed", "skipped")
    ]

"""
Topic service — tree insert, tree retrieval, completion rollup, reparent.
All the business logic for the topics collection lives here.
"""
from datetime import datetime, timezone
from typing import Optional
from beanie import PydanticObjectId

from app.models.topic import Topic
from app.schemas.ai_syllabus import ParsedTopicNode
from app.schemas.topic import TopicResponse


# ── Tree Insert ───────────────────────────────────────────────────────────────

async def insert_topic_tree(
    exam_id: PydanticObjectId,
    nodes: list[ParsedTopicNode],
    parent_id: Optional[PydanticObjectId] = None,
    ancestors: Optional[list[PydanticObjectId]] = None,
    depth: int = 0,
) -> None:
    """
    Recursively insert a parsed topic tree into the topics collection.
    Computes depth, parent_id, ancestors, is_leaf for each node.
    """
    if ancestors is None:
        ancestors = []

    for i, node in enumerate(nodes):
        is_leaf = len(node.children) == 0
        doc = Topic(
            exam_id=exam_id,
            parent_id=parent_id,
            ancestors=ancestors,
            name=node.name,
            depth=depth,
            order_index=i,
            is_leaf=is_leaf,
            weightage=node.weightage,
        )
        await doc.insert()

        if node.children:
            await insert_topic_tree(
                exam_id=exam_id,
                nodes=node.children,
                parent_id=doc.id,
                ancestors=ancestors + [doc.id],
                depth=depth + 1,
            )


# ── Tree Retrieval ────────────────────────────────────────────────────────────

def _build_nested(topics: list[Topic]) -> list[TopicResponse]:
    """
    Convert a flat list of topics (sorted by depth, order_index) into a
    nested TopicResponse tree. O(n) — single pass using a dict.
    """
    id_map: dict[str, TopicResponse] = {}
    roots: list[TopicResponse] = []

    for t in topics:
        node = TopicResponse(
            id=str(t.id),
            exam_id=str(t.exam_id),
            parent_id=str(t.parent_id) if t.parent_id else None,
            name=t.name,
            depth=t.depth,
            order_index=t.order_index,
            is_leaf=t.is_leaf,
            difficulty=t.difficulty,
            estimated_hours=t.estimated_hours,
            weightage=t.weightage,
            prerequisite_topic_id=str(t.prerequisite_topic_id) if t.prerequisite_topic_id else None,
            status=t.status,
            completion_pct=t.completion_pct,
            children=[],
        )
        id_map[str(t.id)] = node

        if t.parent_id is None:
            roots.append(node)
        else:
            parent_node = id_map.get(str(t.parent_id))
            if parent_node:
                parent_node.children.append(node)

    return roots


async def get_topic_tree(exam_id: PydanticObjectId) -> list[TopicResponse]:
    """Return the full nested topic tree for an exam in one DB query."""
    all_topics = (
        await Topic.find(Topic.exam_id == exam_id)
        .sort([("depth", 1), ("order_index", 1)])
        .to_list()
    )
    return _build_nested(all_topics)


# ── Reparent (update ancestors for a moved subtree) ───────────────────────────

async def _rebuild_ancestors(
    topic_id: PydanticObjectId,
    new_ancestors: list[PydanticObjectId],
) -> None:
    """Recursively update ancestors array when a topic is moved."""
    topic = await Topic.get(topic_id)
    if not topic:
        return
    await topic.set({"ancestors": new_ancestors, "updated_at": datetime.now(timezone.utc)})
    # Recurse for children
    children = await Topic.find(Topic.parent_id == topic_id).to_list()
    for child in children:
        await _rebuild_ancestors(child.id, new_ancestors + [topic_id])


async def reparent_topic(
    topic: Topic,
    new_parent_id: Optional[PydanticObjectId],
) -> None:
    """Move a topic to a new parent, rebuilding ancestors for the whole subtree."""
    if new_parent_id is None:
        new_ancestors = []
        new_depth = 0
    else:
        new_parent = await Topic.get(new_parent_id)
        if not new_parent:
            return
        new_ancestors = new_parent.ancestors + [new_parent_id]
        new_depth = new_parent.depth + 1

    await topic.set({
        "parent_id": new_parent_id,
        "ancestors": new_ancestors,
        "depth": new_depth,
        "updated_at": datetime.now(timezone.utc),
    })
    # Rebuild ancestors for all descendants
    children = await Topic.find(Topic.parent_id == topic.id).to_list()
    for child in children:
        await _rebuild_ancestors(child.id, new_ancestors + [topic.id])

    # Update old parent's is_leaf status if it no longer has children
    if topic.parent_id:
        sibling_count = await Topic.find(Topic.parent_id == topic.parent_id).count()
        if sibling_count == 0:
            old_parent = await Topic.get(topic.parent_id)
            if old_parent:
                await old_parent.set({"is_leaf": True})

    # Update new parent's is_leaf status
    if new_parent_id:
        new_parent = await Topic.get(new_parent_id)
        if new_parent and new_parent.is_leaf:
            await new_parent.set({"is_leaf": False})


# ── Completion Rollup ─────────────────────────────────────────────────────────

async def recalculate_completion(topic_id: PydanticObjectId) -> None:
    """
    Recalculate completion_pct for a topic and bubble it up to all ancestors.
    - Leaf topics: completion set directly by Module 3 (study logs).
    - Non-leaf topics: weighted average of children, weighted by estimated_hours.
    """
    topic = await Topic.get(topic_id)
    if topic is None or topic.is_leaf:
        return

    children = await Topic.find(Topic.parent_id == topic_id).to_list()
    if not children:
        return

    total_hours = sum(c.estimated_hours or 1.0 for c in children)
    weighted_pct = sum(
        (c.estimated_hours or 1.0) / total_hours * c.completion_pct
        for c in children
    )
    await topic.set({
        "completion_pct": round(weighted_pct, 2),
        "updated_at": datetime.now(timezone.utc),
    })

    # Bubble up to parent
    if topic.parent_id:
        await recalculate_completion(topic.parent_id)


# ── Module 2 helpers ─────────────────────────────────────────────────────────

async def get_topic_subtree(topic_id: PydanticObjectId) -> list[dict]:
    """
    Return a topic's direct subtopics as plain dicts for the PlannerContext.
    Uses the ancestors index to get all descendants in one query.
    """
    descendants = await Topic.find({"ancestors": topic_id}).to_list()
    return [
        {
            "name": t.name,
            "depth": t.depth,
            "difficulty": t.difficulty,
            "estimated_hours": t.estimated_hours,
            "weightage": t.weightage,
            "status": t.status,
        }
        for t in descendants
    ]


async def get_exam_completion_pct(exam_id: PydanticObjectId) -> float:
    """
    Compute overall exam completion % from leaf topics.
    Returns 0.0 if no topics exist yet.
    """
    pipeline = [
        {"$match": {"exam_id": exam_id, "is_leaf": True}},
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "completed": {
                    "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}
                },
            }
        },
    ]
    results = await Topic.aggregate(pipeline).to_list()
    if not results:
        return 0.0
    row = results[0]
    return round(row["completed"] / row["total"] * 100, 2) if row["total"] else 0.0

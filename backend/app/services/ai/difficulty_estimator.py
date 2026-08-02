import asyncio
import json
from pathlib import Path
from pydantic import ValidationError
from beanie import PydanticObjectId

from app.schemas.ai_syllabus import EnrichedTopicsResponse, EnrichedTopicNode
from app.services.ai.client import call_groq, HEAVY_MODEL
from app.models.topic import Topic

_PROMPT_PATH = Path(__file__).parent / "prompts" / "difficulty_estimator.txt"
SYSTEM_PROMPT = _PROMPT_PATH.read_text()

# Max concurrent AI calls — protects against rate-limit bursts
_SEMAPHORE = asyncio.Semaphore(3)


def _build_topic_payload(topics: list[Topic], all_topics_map: dict) -> list[dict]:
    """Convert a list of Topic documents into the payload shape the AI expects."""
    result = []
    for t in topics:
        children = [
            c for c in all_topics_map.values() if c.parent_id == t.id
        ]
        result.append({
            "id": str(t.id),
            "name": t.name,
            "weightage": t.weightage,
            "children": _build_topic_payload(children, all_topics_map),
        })
    return result


async def _enrich_chunk(
    exam_name: str,
    experience_level: str,
    chunk_payload: list[dict],
) -> EnrichedTopicsResponse:
    """Call the AI for one root-topic chunk and return the validated response."""
    user_msg = (
        f"Exam: {exam_name}\n"
        f"Exam type context: {experience_level}\n\n"
        f"Topics to enrich:\n{json.dumps(chunk_payload, indent=2)}"
    )

    raw = await call_groq(SYSTEM_PROMPT, user_msg, model=HEAVY_MODEL)

    try:
        return EnrichedTopicsResponse.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as e:
        retry_msg = (
            f"{user_msg}\n\n"
            f"Your previous response failed schema validation:\n{e}\n"
            f"Return ONLY corrected JSON matching the required schema exactly."
        )
        raw = await call_groq(SYSTEM_PROMPT, retry_msg, model=HEAVY_MODEL)
        return EnrichedTopicsResponse.model_validate(json.loads(raw))


async def _apply_enrichment(
    enriched_nodes: list[EnrichedTopicNode],
    all_topics_map: dict,
    topic_names_map: dict,
) -> tuple[int, int]:
    """Walk enriched response, update each topic in DB. Returns (success, failed)."""
    success = failed = 0
    for node in enriched_nodes:
        topic = all_topics_map.get(node.id)
        if topic is None:
            failed += 1
            continue
        try:
            update = {
                "difficulty": node.difficulty,
                "estimated_hours": node.estimated_hours,
            }
            if topic.weightage is None and node.weightage is not None:
                update["weightage"] = node.weightage
            # Resolve prerequisite name → id
            if node.prerequisite_topic_name:
                prereq = topic_names_map.get(node.prerequisite_topic_name.lower())
                if prereq and prereq != topic.id:
                    update["prerequisite_topic_id"] = prereq
            await topic.set(update)
            success += 1
        except Exception:
            failed += 1

        # Recurse into children
        if node.children:
            s, f = await _apply_enrichment(node.children, all_topics_map, topic_names_map)
            success += s
            failed += f

    return success, failed


async def enrich_topics(
    exam_id: PydanticObjectId,
    exam_name: str,
    experience_level: str,
) -> tuple[int, int]:
    """
    Agent 2 — Enrich all topics for an exam with difficulty, estimated_hours,
    weightage (if missing), and prerequisites.

    Chunks by root topic so large syllabi don't hit context limits.
    Runs chunks concurrently bounded by a semaphore.
    Returns (enriched_count, failed_count).
    """
    all_topics = await Topic.find(Topic.exam_id == exam_id).to_list()
    all_topics_map: dict[str, Topic] = {str(t.id): t for t in all_topics}
    # Name → id map for prerequisite resolution (lowercase for fuzzy match)
    topic_names_map: dict[str, PydanticObjectId] = {
        t.name.lower(): t.id for t in all_topics
    }

    root_topics = [t for t in all_topics if t.parent_id is None]

    async def process_root(root: Topic) -> tuple[int, int]:
        async with _SEMAPHORE:
            children = [t for t in all_topics if root.id in t.ancestors or t.parent_id == root.id]
            chunk_payload = _build_topic_payload([root], all_topics_map)
            try:
                response = await _enrich_chunk(exam_name, experience_level, chunk_payload)
                return await _apply_enrichment(response.topics, all_topics_map, topic_names_map)
            except Exception:
                return 0, len(children) + 1  # root + all its children count as failed

    results = await asyncio.gather(*[process_root(r) for r in root_topics])
    total_success = sum(r[0] for r in results)
    total_failed = sum(r[1] for r in results)
    return total_success, total_failed

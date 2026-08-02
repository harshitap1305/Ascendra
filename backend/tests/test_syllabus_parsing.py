import pytest
from pydantic import ValidationError
from app.schemas.ai_syllabus import ParsedSyllabusResponse, EnrichedTopicsResponse
from app.services.topic_service import _build_nested


class MockTopic:
    def __init__(self, tid, exam_id, parent_id, name, depth, order_index, is_leaf=True):
        self.id = tid
        self.exam_id = exam_id
        self.parent_id = parent_id
        self.name = name
        self.depth = depth
        self.order_index = order_index
        self.is_leaf = is_leaf
        self.difficulty = None
        self.estimated_hours = None
        self.weightage = None
        self.prerequisite_topic_id = None
        self.status = "not_started"
        self.completion_pct = 0.0


def test_ai_parsed_syllabus_schema_validation():
    valid_payload = {
        "topics": [
            {
                "name": "Engineering Mathematics",
                "order_index": 0,
                "weightage": 15.0,
                "children": [
                    {
                        "name": "Linear Algebra",
                        "order_index": 0,
                        "weightage": 7.5,
                        "children": [
                            {"name": "Matrices", "order_index": 0, "children": []},
                            {"name": "Eigen Values", "order_index": 1, "children": []}
                        ]
                    }
                ]
            }
        ]
    }
    parsed = ParsedSyllabusResponse.model_validate(valid_payload)
    assert len(parsed.topics) == 1
    assert parsed.topics[0].children[0].name == "Linear Algebra"
    assert len(parsed.topics[0].children[0].children) == 2


def test_ai_enriched_syllabus_schema_validation():
    valid_payload = {
        "topics": [
            {
                "id": "item_1",
                "difficulty": "medium",
                "estimated_hours": 4.5,
                "weightage": 10.0,
                "prerequisite_topic_name": None,
                "children": []
            }
        ]
    }
    enriched = EnrichedTopicsResponse.model_validate(valid_payload)
    assert enriched.topics[0].difficulty == "medium"
    assert enriched.topics[0].estimated_hours == 4.5


def test_ai_invalid_schema_throws_validation_error():
    # Missing required field 'estimated_hours'
    invalid_payload = {
        "topics": [
            {
                "id": "item_1",
                "difficulty": "medium",
                "children": []
            }
        ]
    }
    with pytest.raises(ValidationError):
        EnrichedTopicsResponse.model_validate(invalid_payload)


def test_build_nested_tree_algorithm():
    # Test O(n) flat-to-nested tree reconstruction logic
    flat_topics = [
        MockTopic("root_1", "exam_1", None, "Chapter 1", 0, 0, is_leaf=False),
        MockTopic("sub_1", "exam_1", "root_1", "Subtopic 1.1", 1, 0, is_leaf=False),
        MockTopic("sub_2", "exam_1", "root_1", "Subtopic 1.2", 1, 1, is_leaf=True),
        MockTopic("leaf_1", "exam_1", "sub_1", "Leaf 1.1.1", 2, 0, is_leaf=True),
    ]

    tree = _build_nested(flat_topics)
    assert len(tree) == 1
    root = tree[0]
    assert root.name == "Chapter 1"
    assert len(root.children) == 2
    assert root.children[0].name == "Subtopic 1.1"
    assert root.children[1].name == "Subtopic 1.2"
    assert len(root.children[0].children) == 1
    assert root.children[0].children[0].name == "Leaf 1.1.1"

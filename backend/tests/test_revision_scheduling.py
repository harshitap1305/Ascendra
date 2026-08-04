"""
Tests for the Revision Engine in Module 4.
Tests spaced repetition intervals, confidence triggers, and UI re-revision prompt flags.
All tests run purely without an active database.
"""
import pytest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from beanie import PydanticObjectId
from app.services import revision_service


def test_revision_intervals():
    """Verify fixed spaced repetition intervals as designed (1, 3, 7, 15, 30 days)."""
    assert revision_service.REVISION_INTERVALS_DAYS == [1, 3, 7, 15, 30]
    assert len(revision_service.REVISION_INTERVALS_DAYS) == 5
    for i in range(1, 6):
        assert i in revision_service.REVISION_LABELS


@pytest.mark.asyncio
async def test_schedule_revisions_for_topic_creates_5_entries():
    """When a topic completes, 5 spaced revisions should be scheduled."""
    topic = MagicMock()
    topic.id = PydanticObjectId("507f1f77bcf86cd799439011")
    topic.exam_id = PydanticObjectId("507f1f77bcf86cd799439012")
    topic.name = "Dynamic Programming"

    mock_find = MagicMock()
    mock_find.count = AsyncMock(return_value=0)  # No existing revisions

    with patch("app.services.revision_service.RevisionSchedule") as mock_rev_cls:
        # Avoid Beanie collection check by returning SimpleNamespace for doc instantiation
        mock_rev_cls.side_effect = lambda **kwargs: SimpleNamespace(**kwargs)
        mock_rev_cls.find.return_value = mock_find
        mock_rev_cls.insert_many = AsyncMock()

        await revision_service.schedule_revisions_for_topic(topic)

        mock_rev_cls.insert_many.assert_called_once()
        docs = mock_rev_cls.insert_many.call_args[0][0]
        assert len(docs) == 5

        today = date.today()
        for idx, doc in enumerate(docs):
            assert doc.topic_id == topic.id
            assert doc.exam_id == topic.exam_id
            assert doc.topic_name == "Dynamic Programming"
            assert doc.revision_number == idx + 1
            assert doc.trigger_reason == "spaced_repetition"
            assert doc.scheduled_date == today + timedelta(days=revision_service.REVISION_INTERVALS_DAYS[idx])


@pytest.mark.asyncio
async def test_schedule_revisions_skips_if_already_scheduled():
    """Avoid duplicate scheduling if revisions already exist for the topic."""
    topic = MagicMock()
    topic.id = PydanticObjectId("507f1f77bcf86cd799439011")

    mock_find = MagicMock()
    mock_find.count = AsyncMock(return_value=1)  # Revisions already exist

    with patch("app.services.revision_service.RevisionSchedule") as mock_rev_cls:
        mock_rev_cls.find.return_value = mock_find
        mock_rev_cls.insert_many = AsyncMock()
        
        await revision_service.schedule_revisions_for_topic(topic)
        mock_rev_cls.insert_many.assert_not_called()


@pytest.mark.asyncio
async def test_confidence_revision_triggers_on_low_rating_during_checkin():
    """Low confidence (<= 2) during checkin should automatically trigger an urgent revision (number 0)."""
    topic_id = PydanticObjectId("507f1f77bcf86cd799439011")
    mock_topic = MagicMock()
    mock_topic.exam_id = PydanticObjectId("507f1f77bcf86cd799439012")
    mock_topic.name = "Recursion"

    with patch("app.services.revision_service.Topic.get", AsyncMock(return_value=mock_topic)), \
         patch("app.services.revision_service.ConfidenceLog") as mock_log_cls, \
         patch("app.services.revision_service.RevisionSchedule") as mock_rev_cls:

        mock_log = MagicMock()
        mock_log.insert = AsyncMock()
        mock_log_cls.return_value = mock_log

        mock_rev = MagicMock()
        mock_rev.insert = AsyncMock()
        mock_rev_cls.return_value = mock_rev

        await revision_service.maybe_schedule_confidence_revision(topic_id, rating=2, context="checkin")

        mock_log_cls.assert_called_once()
        assert mock_log.insert.called
        mock_rev_cls.assert_called_once()
        assert mock_rev.insert.called
        assert mock_rev_cls.call_args[1]["revision_number"] == 0
        assert mock_rev_cls.call_args[1]["trigger_reason"] == "low_confidence"


@pytest.mark.asyncio
async def test_complete_revision_returns_re_revision_prompt_for_low_confidence():
    """When completing a revision with confidence <= 2, do NOT auto-schedule another; return show_re_revision_prompt=True for user choice in UI."""
    rev_id = PydanticObjectId("507f1f77bcf86cd799439013")
    mock_rev = MagicMock()
    mock_rev.id = rev_id
    mock_rev.topic_id = PydanticObjectId("507f1f77bcf86cd799439011")
    mock_rev.status = "pending"
    mock_rev.save = AsyncMock()

    with patch("app.models.revision_schedule.RevisionSchedule.get", AsyncMock(return_value=mock_rev)), \
         patch("app.services.revision_service.maybe_schedule_confidence_revision", AsyncMock()) as mock_maybe:

        res = await revision_service.complete_revision(rev_id, confidence_rating=1)

        assert mock_rev.status == "done"
        assert mock_rev.re_revision_requested is True
        assert mock_rev.save.called
        assert res["show_re_revision_prompt"] is True
        assert res["status"] == "done"

        # When context is 'revision_done', maybe_schedule_confidence_revision won't auto-schedule extra revision
        mock_maybe.assert_called_once_with(
            topic_id=mock_rev.topic_id,
            rating=1,
            context="revision_done",
            revision_schedule_id=mock_rev.id,
        )

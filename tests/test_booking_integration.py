"""Tests for booking ↔ quest_generation integration."""

import asyncio
import os
import sys
import pytest

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_root, "backend"))

# Force DEMO_MODE so config.py doesn't require real secrets
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from agents.quest_generation.models import (
    ActivityRef,
    NarrativeUniverse,
    QuestOutput,
    Step,
)
from agents.booking.booking_agent import prepare_booking_from_activity
from agents.booking.models import BookingIntent
from agents.integration.service import prepare_quest_bookings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_quest(steps: list[Step]) -> QuestOutput:
    """Minimal QuestOutput with given steps."""
    return QuestOutput(
        narrative_universe=NarrativeUniverse(hook="test hook"),
        steps=steps,
    )


# ---------------------------------------------------------------------------
# 1. ActivityRef.booking_required default
# ---------------------------------------------------------------------------

def test_activity_ref_booking_required_default():
    ref = ActivityRef(name="Test")
    assert ref.booking_required is False


# ---------------------------------------------------------------------------
# 2. Adapter returns None for empty name
# ---------------------------------------------------------------------------

def test_adapter_returns_none_for_empty_name():
    ref = ActivityRef(name="", booking_url="https://example.com")
    result = asyncio.run(prepare_booking_from_activity(ref, "Cannes"))
    assert result is None


# ---------------------------------------------------------------------------
# 3. Adapter returns None for empty booking_url
# ---------------------------------------------------------------------------

def test_adapter_returns_none_for_empty_url():
    ref = ActivityRef(name="Resto Chez Paul", booking_url="")
    result = asyncio.run(prepare_booking_from_activity(ref, "Cannes"))
    assert result is None


# ---------------------------------------------------------------------------
# 4. Adapter maps fields correctly
# ---------------------------------------------------------------------------

def test_adapter_maps_fields_correctly():
    ref = ActivityRef(
        name="Kayak Lérins",
        address="Port de Cannes",
        price_eur=20.0,
        booking_url="https://kayak-lerins.com/book",
        booking_required=True,
        category="sport",
    )
    intent = asyncio.run(prepare_booking_from_activity(ref, "Cannes"))
    assert intent is not None
    assert intent.activity_name == "Kayak Lérins"
    assert intent.booking_url == "https://kayak-lerins.com/book"
    # DEMO_MODE caps at min(budget_eur, 25.0), so 20.0 passes through
    assert intent.price_eur == 20.0


# ---------------------------------------------------------------------------
# 5. prepare_quest_bookings — fallback filter (booking_url without booking_required)
# ---------------------------------------------------------------------------

def test_prepare_quest_bookings_fallback_filter():
    """booking_required=False but booking_url set → still picked up by OR filter."""
    step = Step(
        step_id=1,
        activity=ActivityRef(
            name="Test Resto",
            booking_url="https://example.com/book",
            booking_required=False,
        ),
    )
    quest = _make_quest([step])
    result = asyncio.run(prepare_quest_bookings(quest))
    assert len(result) == 1
    assert result[0].activity_name == "Test Resto"


# ---------------------------------------------------------------------------
# 6. prepare_quest_bookings — skips narrative-only steps
# ---------------------------------------------------------------------------

def test_prepare_quest_bookings_skips_narrative_steps():
    """Steps with no name/url are filtered out."""
    steps = [
        Step(step_id=1, activity=ActivityRef(name="", booking_url="")),
        Step(step_id=2, activity=ActivityRef(name="Walk in Park")),
    ]
    quest = _make_quest(steps)
    result = asyncio.run(prepare_quest_bookings(quest))
    assert len(result) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

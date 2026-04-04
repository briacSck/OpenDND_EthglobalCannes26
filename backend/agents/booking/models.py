"""Booking models — intent and result for activity reservations."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BookingIntent(BaseModel):
    """What the booking agent plans to do before attempting checkout."""

    activity_name: str
    booking_url: str = ""
    price_eur: float = 0
    steps_to_complete: list[str] = Field(
        default_factory=list,
        description="Ordered steps the agent will take (e.g. 'select date', 'fill guest count')",
    )
    requires_human_action: bool = Field(
        default=True,
        description="True if payment form, login, or CAPTCHA blocks automation",
    )
    reason: str | None = Field(
        default=None,
        description="Why human action is needed, or None if fully automatable",
    )


class BookingResult(BaseModel):
    """Outcome of a booking attempt."""

    status: str = Field(description="completed | completed_unverified | pending_human | failed")
    booking_ref: str | None = None
    confirmation_url: str | None = None
    instructions: str | None = Field(
        default=None,
        description="Human-facing instructions when status is pending_human or failed",
    )


# ---------------------------------------------------------------------------
# Web discovery & form-filling models
# ---------------------------------------------------------------------------


class BookingOption(BaseModel):
    """A discovered booking option from web search."""

    name: str
    url: str
    price_eur: float | None = None
    source: str = Field(default="", description="getyourguide | tripadvisor | viator | direct | demo")
    availability_hint: str = Field(default="", description="available | few spots left | unknown")
    score: float = Field(default=0, description="LLM-assigned relevance score 0-1")


class AvailabilityResult(BaseModel):
    """Result of checking availability on a booking page."""

    available: bool = False
    available_slots: list[str] = Field(default_factory=list)
    price_confirmed: float | None = None
    needs_human: bool = False
    reason: str = ""


class BookingFormData(BaseModel):
    """Data needed to fill booking forms."""

    player_name: str = ""
    player_email: str = ""
    datetime_str: str = Field(default="", description="ISO format: 2026-04-05 10:00")
    guest_count: int = 1
    location: str = ""


class NavigationResult(BaseModel):
    """Result of the LLM-driven multi-step booking navigation."""

    success: bool = False
    final_url: str = ""
    booking_ref: str | None = None
    steps_taken: list[str] = Field(default_factory=list)
    reason: str = Field(default="", description="Why navigation stopped, if not success")
    fields_filled: dict = Field(default_factory=dict)

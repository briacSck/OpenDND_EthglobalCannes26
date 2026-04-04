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

    status: str = Field(description="completed | pending_human | failed")
    booking_ref: str | None = None
    confirmation_url: str | None = None
    instructions: str | None = Field(
        default=None,
        description="Human-facing instructions when status is pending_human or failed",
    )

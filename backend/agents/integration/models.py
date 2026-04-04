"""Integration models — canonical data shapes for the app backend to consume.

These models are transport-agnostic. The app backend can expose them
over REST, SSE, WebSocket, or any other protocol.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Inputs — what the app backend sends to OpenClaw service functions
# ---------------------------------------------------------------------------


class PlayerMessageInput(BaseModel):
    """Player sends a direct message to a character."""
    session_id: str
    character_name: str
    content: str


class PlayerActionInput(BaseModel):
    """Player performs a generic action (move, voice, custom, etc.)."""
    session_id: str
    action_type: str = Field(description="message | voice | move | ignore | custom")
    content: str = ""
    target_character: str = ""
    gps_coords: list[float] | None = None


class VoiceProofInput(BaseModel):
    """Audio proof from Meta Glasses or phone mic."""
    session_id: str
    audio_b64: str = Field(description="Base64-encoded audio data")
    encoding: str = Field(default="pcm_16khz", description="pcm_16khz | aac | opus")
    duration_ms: int = 0


class ImageProofInput(BaseModel):
    """Single image proof from glasses camera or phone."""
    session_id: str
    frame_b64: str = Field(description="Base64-encoded image data")
    media_type: str = Field(default="image/jpeg", description="image/jpeg | image/png")


class VideoProofInput(BaseModel):
    """Video proof — a frame will be extracted automatically."""
    session_id: str
    video_b64: str = Field(description="Base64-encoded MP4 video")


class BookingConfirmationInput(BaseModel):
    """Player confirms a pending booking."""
    session_id: str
    booking_ref: str = ""


# ---------------------------------------------------------------------------
# Outputs — what OpenClaw returns to the app backend
# ---------------------------------------------------------------------------


class RuntimeEventEnvelope(BaseModel):
    """Stable JSON-safe wrapper around OrchestratorEvent for external consumers.

    The app backend should use `type` for routing (e.g. SSE event names)
    and `payload` for the full event data.
    """
    event_id: str
    type: str = Field(description=(
        "character_message | artifact | timer | group_chat | "
        "forwarded_message | arg_event | checkpoint.verified | "
        "booking.prepared | booking.completed | booking.pending_human | "
        "quest.reward.confirmed"
    ))
    ts: str = Field(description="ISO 8601 timestamp")
    character_name: str | None = Field(default=None, description="Character involved, if any")
    content: str = Field(default="", description="Primary text content")
    voice_line: str | None = Field(
        default=None,
        description="Voice script for TTS delivery. From event.voice_script when available, else None.",
    )
    payload: dict = Field(
        default_factory=dict,
        description="Full event data (model_dump) for extensibility",
    )


class QuestRecapResponse(BaseModel):
    """Post-quest recap returned after quest completion."""
    quest_id: str
    session_id: str
    narrative_summary: str = ""
    highlights: list[str] = Field(default_factory=list)
    next_quest_teaser: str = ""
    grade: str = Field(default="C", description="A-F grade")
    reward_tx_hash: str | None = None
    memory_root_hash: str | None = None

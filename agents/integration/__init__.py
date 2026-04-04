"""Integration layer — service functions and models for the app backend."""

from agents.integration.models import (
    BookingConfirmationInput,
    ImageProofInput,
    PlayerActionInput,
    PlayerMessageInput,
    QuestRecapResponse,
    RuntimeEventEnvelope,
    VideoProofInput,
    VoiceProofInput,
)
from agents.integration.serializer import serialize_event, serialize_events
from agents.integration.service import (
    confirm_booking,
    generate_quest_recap,
    handle_player_action,
    handle_player_message,
    prepare_quest_bookings,
    start_quest_session,
    submit_image_or_video_proof,
    submit_voice_proof,
)

__all__ = [
    # Models
    "BookingConfirmationInput",
    "ImageProofInput",
    "PlayerActionInput",
    "PlayerMessageInput",
    "QuestRecapResponse",
    "RuntimeEventEnvelope",
    "VideoProofInput",
    "VoiceProofInput",
    # Serialization
    "serialize_event",
    "serialize_events",
    # Service functions
    "confirm_booking",
    "generate_quest_recap",
    "handle_player_action",
    "handle_player_message",
    "prepare_quest_bookings",
    "start_quest_session",
    "submit_image_or_video_proof",
    "submit_voice_proof",
]

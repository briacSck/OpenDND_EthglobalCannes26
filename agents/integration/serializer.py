"""Event serializer — converts internal OrchestratorEvent to stable RuntimeEventEnvelope."""

from __future__ import annotations

from agents.integration.models import RuntimeEventEnvelope
from agents.quest_runtime.models import OrchestratorEvent


def serialize_event(event: OrchestratorEvent) -> RuntimeEventEnvelope:
    """Convert a single OrchestratorEvent into a transport-agnostic envelope.

    - voice_line comes from event.voice_script when non-empty, otherwise None.
    - character_name comes from event.character when non-empty, otherwise None.
    - payload is the full model_dump for extensibility.
    """
    return RuntimeEventEnvelope(
        event_id=event.event_id,
        type=event.type,
        ts=event.timestamp,
        character_name=event.character if event.character else None,
        content=event.content,
        voice_line=event.voice_script if event.voice_script else None,
        payload=event.model_dump(),
    )


def serialize_events(events: list[OrchestratorEvent]) -> list[RuntimeEventEnvelope]:
    """Batch conversion of events."""
    return [serialize_event(e) for e in events]

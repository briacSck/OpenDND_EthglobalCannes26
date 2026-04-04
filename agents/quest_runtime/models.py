"""Runtime models — session state, player actions, orchestrator events."""

from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class PlayerAction(BaseModel):
    """An action the player takes during the quest."""
    type: str = Field(description="message | voice | move | ignore | custom")
    content: str = Field(default="", description="Text content of the action")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    gps_coords: list[float] | None = Field(default=None, description="[lat, lon] if available")
    target_character: str = Field(default="", description="Character the player is interacting with, if any")


class Artifact(BaseModel):
    """A generated artifact sent to the player during the quest."""
    type: str = Field(description="surveillance_photo | classified_document | intercepted_audio | handwritten_note | map | coded_message")
    description: str = ""
    generation_prompt: str = Field(default="", description="Prompt to generate this artifact (for image/audio gen)")


class OrchestratorEvent(BaseModel):
    """An event the orchestrator decides to send to the player."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = Field(description="character_message | artifact | timer | group_chat | forwarded_message | arg_event")
    character: str = Field(default="", description="Which character sends this, if applicable")
    content: str = Field(default="", description="Text content of the event")
    voice_script: str = Field(default="", description="Script for voice delivery if applicable")
    artifact: Artifact | None = None
    timer_seconds: int = Field(default=0, description="Countdown duration if type is timer")
    arg_channel: str = Field(default="", description="email | sms | social — for ARG events")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ConversationEntry(BaseModel):
    """A single message in a character-player conversation."""
    role: str = Field(description="player | character")
    character_name: str = ""
    content: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class CharacterTrust(BaseModel):
    """Trust level between a character and the player."""
    character_name: str
    trust_level: int = 50
    interaction_count: int = 0
    last_action: str = ""


class SessionState(BaseModel):
    """Current state of a live quest session."""
    current_step: int = 0
    beats_completed: list[int] = Field(default_factory=list)
    characters_trust: list[CharacterTrust] = Field(default_factory=list)
    narrative_arc: str = Field(default="", description="Which possible_arc the story is currently following")
    time_since_last_event_seconds: int = 0
    total_elapsed_seconds: int = 0
    player_speed: str = Field(default="normal", description="slow | normal | fast — based on movement/response time")


class QuestSession(BaseModel):
    """A live quest session."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    quest_id: str = ""
    player_alias: str = ""
    state: SessionState = Field(default_factory=SessionState)
    events_log: list[OrchestratorEvent] = Field(default_factory=list)
    actions_log: list[PlayerAction] = Field(default_factory=list)
    conversations: dict[str, list[ConversationEntry]] = Field(default_factory=dict, description="Per-character conversation history: {character_name: [entries]}")
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    active: bool = True
    completed_at: str | None = Field(default=None, description="ISO timestamp set once when quest completion is persisted")


class PlayStartRequest(BaseModel):
    """Request to start a live quest session."""
    quest_id: str
    player_name: str = ""
    allow_arg: bool = Field(default=False, description="Player consents to ARG events (fake emails, SMS, social follows)")
    player_email: str = Field(default="", description="For ARG email events, if allowed")
    player_phone: str = Field(default="", description="For ARG SMS events, if allowed")


class PlayActionRequest(BaseModel):
    """Request from the player during a live session."""
    session_id: str
    action: PlayerAction


class PlayMessageRequest(BaseModel):
    """Player sends a direct message to a specific character."""
    session_id: str
    character_name: str = Field(description="Name of the character to talk to")
    content: str = Field(description="The player's message")


class PlayHeartbeatRequest(BaseModel):
    """Heartbeat ping from the client to keep the session alive and trigger idle events."""
    session_id: str
    gps_coords: list[float] | None = None
    weather: str = ""

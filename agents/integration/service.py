"""Integration service layer — pure async functions the app backend calls.

Every function accepts resolved objects (quest, session, orchestrator) as
parameters.  The caller (main.py endpoints or the app backend) is responsible
for looking up these objects from its stores.  This keeps the service layer
free of circular imports and easy to test.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from agents.booking.booking_agent import prepare_booking, prepare_booking_from_activity, complete_booking
from agents.booking.models import BookingIntent, BookingResult
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
from agents.integration.serializer import serialize_events
from agents.memory import index as memory_index
from agents.memory.player_profile import (
    QuestSummary,
    load_player_profile,
    save_quest_memory,
    update_player_profile,
)
from agents.proof.image_proof import extract_frame_from_video, verify_image
from agents.proof.models import ProofResult
from agents.proof.recap import generate_recap
from agents.proof.voice_proof import verify_voice
from agents.quest_generation.models import QuestOutput
from agents.quest_runtime.character_agent import CharacterAgent
from agents.quest_runtime.models import (
    CharacterTrust,
    OrchestratorEvent,
    PlayerAction,
    QuestSession,
    SessionState,
)
from agents.quest_runtime.orchestrator import OrchestratorAgent
from config import DEMO_MODE

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. start_quest_session
# ---------------------------------------------------------------------------


async def start_quest_session(
    quest: QuestOutput,
    player_name: str = "",
    allow_arg: bool = False,
) -> tuple[QuestSession, OrchestratorAgent, list[RuntimeEventEnvelope]]:
    """Create a new quest session, orchestrator, and fire the opening sequence.

    Returns (session, orchestrator, serialized_events).
    The caller must store session and orchestrator in its own registry.
    """
    session = QuestSession(
        quest_id=quest.quest_id,
        player_alias=quest.alias or "Agent",
        state=SessionState(
            current_step=quest.steps[0].step_id if quest.steps else 0,
            characters_trust=[
                CharacterTrust(character_name=c.name, trust_level=50)
                for c in quest.characters
            ],
        ),
    )

    # Load player memory
    memory_context = ""
    if not DEMO_MODE:
        player_id = player_name or session.player_alias or session.session_id
        try:
            profile = await load_player_profile(player_id)
            if profile and profile.completed_quests:
                themes = list({q.theme for q in profile.completed_quests if q.theme})
                last = profile.completed_quests[-1]
                memory_context = (
                    f"Player history: completed {len(profile.completed_quests)} quests. "
                    f"Themes: {themes}. "
                    f"Preferences: {profile.extracted_preferences}. "
                    f"Last quest grade: {last.grade or 'N/A'}."
                )
        except Exception:
            logger.debug("Could not load player memory for %s", player_id, exc_info=True)

    orchestrator = OrchestratorAgent(
        quest=quest,
        session=session,
        allow_arg=allow_arg,
        memory_context=memory_context,
    )

    events = await orchestrator.react(trigger="start")
    return session, orchestrator, serialize_events(events)


# ---------------------------------------------------------------------------
# 1b. prepare_quest_bookings
# ---------------------------------------------------------------------------


async def prepare_quest_bookings(quest: QuestOutput) -> list[BookingIntent]:
    """Extract bookable activities from a generated quest and prepare BookingIntents.

    Call after quest generation, before session start. The app backend uses the
    returned intents to show the player which activities need advance booking.

    Filter uses OR: booking_required OR booking_url present. Before the Curator
    prompt update is fully effective, booking_required will be False on all
    existing quests — booking_url != "" is the reliable fallback for now.
    """
    quest_location = quest.narrative_universe.context or ""
    intents: list[BookingIntent] = []

    for step in quest.steps:
        activity = step.activity
        if not activity.booking_required and not activity.booking_url:
            continue
        intent = await prepare_booking_from_activity(activity, quest_location)
        if intent is not None:
            intents.append(intent)

    return intents


# ---------------------------------------------------------------------------
# 2. handle_player_message
# ---------------------------------------------------------------------------


async def handle_player_message(
    inp: PlayerMessageInput,
    quest: QuestOutput,
    session: QuestSession,
    orchestrator: OrchestratorAgent,
) -> tuple[str, list[RuntimeEventEnvelope]]:
    """Player sends a message to a character.

    Returns (character_response_text, all_events_as_envelopes).
    Raises ValueError if character not found.
    """
    char_agent = orchestrator.get_character_agent(inp.character_name)
    if not char_agent:
        raise ValueError(f"Character '{inp.character_name}' not found in this quest.")

    # Update timing
    _update_timing(session)

    # Character responds
    char_response = await char_agent.respond(inp.content)
    session.events_log.append(char_response)

    # Orchestrator may trigger follow-ups
    player_action = PlayerAction(
        type="message",
        content=inp.content,
        target_character=inp.character_name,
    )
    followup_events = await orchestrator.react(
        trigger="player_message",
        player_action=player_action,
    )

    all_events = [char_response] + followup_events

    # Check completion
    await _check_quest_completion(session, quest)

    return char_response.content, serialize_events(all_events)


# ---------------------------------------------------------------------------
# 3. handle_player_action
# ---------------------------------------------------------------------------


async def handle_player_action(
    inp: PlayerActionInput,
    quest: QuestOutput,
    session: QuestSession,
    orchestrator: OrchestratorAgent,
) -> list[RuntimeEventEnvelope]:
    """Player performs a generic action. Returns orchestrator response events."""
    _update_timing(session)

    action = PlayerAction(
        type=inp.action_type,
        content=inp.content,
        target_character=inp.target_character,
        gps_coords=inp.gps_coords,
    )

    events = await orchestrator.react(trigger="action", player_action=action)

    await _check_quest_completion(session, quest)

    return serialize_events(events)


# ---------------------------------------------------------------------------
# 4. submit_voice_proof
# ---------------------------------------------------------------------------


async def submit_voice_proof(
    inp: VoiceProofInput,
    quest: QuestOutput,
    session: QuestSession,
) -> ProofResult:
    """Verify audio proof against the current step's verification target."""
    verification = _resolve_verification(quest, session)

    result = await verify_voice(
        audio_b64=inp.audio_b64,
        encoding=inp.encoding,
        duration_ms=inp.duration_ms,
        verification=verification,
    )
    result.step_id = session.state.current_step

    if result.verified:
        session.events_log.append(OrchestratorEvent(
            type="checkpoint.verified",
            content=f"Voice proof verified: {result.matched_keyword or 'match'}",
        ))

    return result


# ---------------------------------------------------------------------------
# 5. submit_image_or_video_proof
# ---------------------------------------------------------------------------


async def submit_image_or_video_proof(
    inp: ImageProofInput | VideoProofInput,
    quest: QuestOutput,
    session: QuestSession,
) -> ProofResult:
    """Verify image or video proof against the current step's verification target."""
    verification = _resolve_verification(quest, session)

    if isinstance(inp, VideoProofInput):
        frame_b64, media_type = await extract_frame_from_video(inp.video_b64)
    else:
        frame_b64 = inp.frame_b64
        media_type = inp.media_type

    result = await verify_image(
        frame_b64=frame_b64,
        media_type=media_type,
        verification=verification,
    )
    result.step_id = session.state.current_step

    if result.verified:
        session.events_log.append(OrchestratorEvent(
            type="checkpoint.verified",
            content=f"Image proof verified: {result.description or 'match'}",
        ))
        # Store best description for recap
        if result.description:
            session.best_proof_description = result.description

    return result


# ---------------------------------------------------------------------------
# 6. confirm_booking
# ---------------------------------------------------------------------------


async def confirm_booking(
    inp: BookingConfirmationInput,
    session: QuestSession,
    orchestrator: OrchestratorAgent,
) -> list[RuntimeEventEnvelope]:
    """Player confirms a pending booking. Returns narration events."""
    booking_event = OrchestratorEvent(
        type="booking.completed",
        content=json.dumps({"booking_ref": inp.booking_ref}, ensure_ascii=False),
    )
    session.events_log.append(booking_event)

    # Orchestrator triggers a character to narrate the confirmation
    narration_events = await orchestrator.react(
        trigger="action",
        player_action=PlayerAction(
            type="custom",
            content=f"[booking:completed] Réservation confirmée (ref: {inp.booking_ref}).",
        ),
    )

    return serialize_events([booking_event] + narration_events)


# ---------------------------------------------------------------------------
# 7. generate_quest_recap
# ---------------------------------------------------------------------------


async def generate_quest_recap(
    quest: QuestOutput,
    session: QuestSession,
) -> QuestRecapResponse:
    """Generate a post-quest recap for a completed session."""
    # Find reward tx_hash from events
    reward_tx_hash = None
    for e in session.events_log:
        if e.type == "quest.reward.confirmed":
            reward_tx_hash = e.content
            break

    # Find memory root_hash from index
    memory_root_hash = None
    root_hashes = memory_index.get_quest_root_hashes_for_quest(quest.quest_id)
    if root_hashes:
        memory_root_hash = root_hashes[-1]

    recap_data = await generate_recap(
        quest=quest,
        session=session,
        reward_tx_hash=reward_tx_hash,
        memory_root_hash=memory_root_hash,
        best_frame_description=session.best_proof_description,
    )

    return QuestRecapResponse(
        quest_id=quest.quest_id,
        session_id=session.session_id,
        narrative_summary=recap_data.get("narrative_summary", ""),
        highlights=recap_data.get("highlights", []),
        next_quest_teaser=recap_data.get("next_quest_teaser", ""),
        grade=recap_data.get("grade", "C"),
        reward_tx_hash=reward_tx_hash,
        memory_root_hash=memory_root_hash,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _update_timing(session: QuestSession) -> None:
    """Refresh elapsed-time fields on the session."""
    started = datetime.fromisoformat(session.started_at)
    session.state.total_elapsed_seconds = int((datetime.now() - started).total_seconds())
    if session.events_log:
        last_event_time = datetime.fromisoformat(session.events_log[-1].timestamp)
        session.state.time_since_last_event_seconds = int(
            (datetime.now() - last_event_time).total_seconds()
        )


def _resolve_verification(quest: QuestOutput, session: QuestSession):
    """Get the Verification object for the current step."""
    for step in quest.steps:
        if step.step_id == session.state.current_step:
            return step.verification
    raise ValueError(
        f"Step {session.state.current_step} not found in quest {quest.quest_id}"
    )


async def _check_quest_completion(
    session: QuestSession, quest: QuestOutput
) -> dict | None:
    """Persist quest memory + update player profile when the quest is done.

    Returns a completion dict on success, None if not yet complete or already
    persisted.  Retry-safe: partial failures leave completed_at as None.
    """
    if session.completed_at is not None:
        return None
    if session.state.current_step < len(quest.steps):
        return None

    try:
        quest_root_hash = await save_quest_memory(quest, session)

        started = datetime.fromisoformat(session.started_at)
        duration_min = int((datetime.now() - started).total_seconds() / 60)
        player_id = session.player_alias or session.session_id

        summary = QuestSummary(
            quest_id=quest.quest_id,
            run_id=session.session_id,
            root_hash=quest_root_hash,
            theme=quest.tone,
            duration_minutes=duration_min,
        )

        await update_player_profile(player_id, summary)

        session.completed_at = datetime.now().isoformat()
        session.active = False

        return {
            "quest_completed": True,
            "quest_root_hash": quest_root_hash,
            "duration_minutes": duration_min,
            "player_id": player_id,
        }
    except Exception:
        logger.exception(
            "Quest completion persistence failed for session %s",
            session.session_id,
        )
        return None

"""OpenD&D — Quest Research, Generation & Runtime API."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from agents.city_research.models import QuestRequest as ResearchRequest, CityContext
from agents.city_research.agent import CityResearchAgent
from agents.quest_generation.models import QuestRequest, QuestOutput
from agents.quest_generation import pipeline
from agents.quest_runtime.models import (
    QuestSession, SessionState, CharacterTrust, PlayerAction,
    PlayStartRequest, PlayActionRequest, PlayHeartbeatRequest,
    PlayMessageRequest, OrchestratorEvent,
)
from agents.quest_runtime.orchestrator import OrchestratorAgent
from agents.memory.player_profile import (
    PlayerProfile, QuestSummary,
    save_quest_memory, update_player_profile, load_player_profile,
)
from agents.reward.hedera_reward import RewardTx, trigger_reward
from agents.booking.booking_agent import prepare_booking, complete_booking
from agents.booking.models import BookingIntent, BookingResult
from agents.memory import index as memory_index
from config import DEMO_MODE

logger = logging.getLogger(__name__)

app = FastAPI(title="OpenD&D", description="AI-powered real-life quest system")

# In-memory stores (replace with DB later)
_quests: dict[str, QuestOutput] = {}
_sessions: dict[str, QuestSession] = {}
_orchestrators: dict[str, OrchestratorAgent] = {}


# --- Existing endpoints ---

@app.post("/research", response_model=CityContext)
async def research_city(request: ResearchRequest) -> CityContext:
    """Run the City Research Agent to gather data for a quest."""
    agent = CityResearchAgent()
    context = await agent.research(request.model_dump())
    return context


@app.post("/generate", response_model=QuestOutput)
async def generate_quest(request: QuestRequest) -> QuestOutput:
    """Full pipeline: research city + generate quest."""
    agent = CityResearchAgent()
    context = await agent.research(request.model_dump())
    quest = await pipeline.generate_quest(request, context)
    # Store for runtime
    _quests[quest.quest_id] = quest
    return quest


# --- Runtime endpoints ---

@app.post("/play/start")
async def play_start(request: PlayStartRequest) -> dict:
    """Start a live quest session. Returns session_id and the first events."""

    quest = _quests.get(request.quest_id)
    if not quest:
        raise HTTPException(status_code=404, detail=f"Quest {request.quest_id} not found. Generate it first via /generate.")

    # Create session
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
    _sessions[session.session_id] = session

    # Load player memory (skip in DEMO_MODE or if no profile exists)
    memory_context = ""
    if not DEMO_MODE:
        player_id = session.player_alias or session.session_id
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

    # Create orchestrator
    orchestrator = OrchestratorAgent(
        quest=quest,
        session=session,
        allow_arg=request.allow_arg,
        memory_context=memory_context,
    )
    _orchestrators[session.session_id] = orchestrator

    # Trigger the opening sequence
    events = await orchestrator.react(trigger="start")

    return {
        "session_id": session.session_id,
        "player_alias": session.player_alias,
        "quest_title": quest.title,
        "tone": quest.tone,
        "events": [e.model_dump() for e in events],
    }


@app.post("/play/action")
async def play_action(request: PlayActionRequest) -> dict:
    """Player sends an action. Returns the orchestrator's response events."""

    session = _sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if not session.active:
        raise HTTPException(status_code=400, detail="Session is no longer active.")

    orchestrator = _orchestrators.get(request.session_id)
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not found for session.")

    # Update timing
    if session.events_log:
        last_event_time = datetime.fromisoformat(session.events_log[-1].timestamp)
        now = datetime.now()
        session.state.time_since_last_event_seconds = int((now - last_event_time).total_seconds())
    started = datetime.fromisoformat(session.started_at)
    session.state.total_elapsed_seconds = int((datetime.now() - started).total_seconds())

    events = await orchestrator.react(trigger="action", player_action=request.action)

    quest = _quests.get(session.quest_id)
    completion = await _check_quest_completion(session, quest) if quest else None

    response: dict = {
        "session_id": session.session_id,
        "events": [e.model_dump() for e in events],
        "state": {
            "current_step": session.state.current_step,
            "elapsed_minutes": session.state.total_elapsed_seconds // 60,
            "characters_trust": {
                ct.character_name: ct.trust_level
                for ct in session.state.characters_trust
            },
        },
    }
    if completion:
        response["completion"] = completion
    return response


@app.post("/play/message")
async def play_message(request: PlayMessageRequest) -> dict:
    """Player sends a direct message to a specific character. Returns the character's
    response + any orchestrator-triggered follow-up events (chime-ins, beats, artifacts)."""

    session = _sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if not session.active:
        raise HTTPException(status_code=400, detail="Session is no longer active.")

    orchestrator = _orchestrators.get(request.session_id)
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not found for session.")

    # Find the character agent
    char_agent = orchestrator.get_character_agent(request.character_name)
    if not char_agent:
        raise HTTPException(
            status_code=404,
            detail=f"Character '{request.character_name}' not found in this quest.",
        )

    # Update timing
    started = datetime.fromisoformat(session.started_at)
    session.state.total_elapsed_seconds = int((datetime.now() - started).total_seconds())
    if session.events_log:
        last_event_time = datetime.fromisoformat(session.events_log[-1].timestamp)
        session.state.time_since_last_event_seconds = int((datetime.now() - last_event_time).total_seconds())

    # 1. Character agent responds directly
    char_response = await char_agent.respond(request.content)
    session.events_log.append(char_response)

    # 2. Notify orchestrator — it may trigger follow-up events (other perso chime in, beat, artifact)
    player_action = PlayerAction(
        type="message",
        content=request.content,
        target_character=request.character_name,
    )
    followup_events = await orchestrator.react(
        trigger="player_message",
        player_action=player_action,
    )

    all_events = [char_response] + followup_events

    quest = _quests.get(session.quest_id)
    completion = await _check_quest_completion(session, quest) if quest else None

    response: dict = {
        "session_id": session.session_id,
        "character": request.character_name,
        "response": char_response.content,
        "events": [e.model_dump() for e in all_events],
        "state": {
            "current_step": session.state.current_step,
            "elapsed_minutes": session.state.total_elapsed_seconds // 60,
            "characters_trust": {
                ct.character_name: ct.trust_level
                for ct in session.state.characters_trust
            },
        },
    }
    if completion:
        response["completion"] = completion
    return response


@app.post("/play/heartbeat")
async def play_heartbeat(request: PlayHeartbeatRequest) -> dict:
    """Heartbeat ping. Triggers idle events if the player has been inactive."""

    session = _sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if not session.active:
        return {"session_id": session.session_id, "events": [], "message": "Session ended."}

    orchestrator = _orchestrators.get(request.session_id)
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not found.")

    # Update timing
    started = datetime.fromisoformat(session.started_at)
    session.state.total_elapsed_seconds = int((datetime.now() - started).total_seconds())

    if session.events_log:
        last_event_time = datetime.fromisoformat(session.events_log[-1].timestamp)
        session.state.time_since_last_event_seconds = int((datetime.now() - last_event_time).total_seconds())
    else:
        session.state.time_since_last_event_seconds = session.state.total_elapsed_seconds

    # Determine trigger
    if session.state.time_since_last_event_seconds > 300:  # 5 min idle
        trigger = "idle"
    else:
        trigger = "heartbeat"

    events = await orchestrator.react(trigger=trigger)

    quest = _quests.get(session.quest_id)
    completion = await _check_quest_completion(session, quest) if quest else None

    response: dict = {
        "session_id": session.session_id,
        "events": [e.model_dump() for e in events],
        "state": {
            "current_step": session.state.current_step,
            "elapsed_minutes": session.state.total_elapsed_seconds // 60,
            "idle_seconds": session.state.time_since_last_event_seconds,
        },
    }
    if completion:
        response["completion"] = completion
    return response


@app.get("/play/status/{session_id}")
async def play_status(session_id: str) -> dict:
    """Get the current status of a quest session."""

    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    quest = _quests.get(session.quest_id)

    return {
        "session_id": session.session_id,
        "quest_title": quest.title if quest else "?",
        "active": session.active,
        "player_alias": session.player_alias,
        "state": session.state.model_dump(),
        "events_count": len(session.events_log),
        "actions_count": len(session.actions_log),
        "last_event": session.events_log[-1].model_dump() if session.events_log else None,
    }


# --- Reward endpoint ---


@app.post("/quests/{quest_id}/reward", response_model=RewardTx)
async def quest_reward(quest_id: str, player_wallet: str = "", grade: str = "") -> RewardTx:
    """Trigger an on-chain reward for a completed quest.

    Reads the memory_root_hash from the local index to anchor the off-chain
    quest memory on Hedera, then returns the RewardTx receipt.
    """
    # Look up the most recent memory root_hash for this quest
    root_hashes = memory_index.get_quest_root_hashes_for_quest(quest_id)
    if not root_hashes:
        raise HTTPException(
            status_code=404,
            detail=f"No quest memory found for quest {quest_id}. Complete the quest first.",
        )
    memory_root_hash = root_hashes[-1]  # most recent run

    reward_tx = await trigger_reward(
        quest_id=quest_id,
        player_wallet=player_wallet,
        grade=grade,
        memory_root_hash=memory_root_hash,
    )

    # Find the session for this quest and mark reward confirmed
    for session in _sessions.values():
        if session.quest_id == quest_id and session.completed_at is not None:
            session.events_log.append(
                OrchestratorEvent(
                    type="quest.reward.confirmed",
                    content=f"Reward confirmed: tx={reward_tx.tx_hash}",
                )
            )
            break

    return reward_tx


# --- Booking endpoint ---


@app.post("/quests/{quest_id}/booking")
async def quest_booking(quest_id: str, session_id: str = "") -> dict:
    """Prepare and attempt a booking for the current step's activity.

    Finds the active session's current step, extracts its activity, runs
    prepare_booking + complete_booking, then notifies the orchestrator via
    an event so a character can narrate the outcome.
    If booking fails: the checkpoint is NOT blocked — falls back to manual proof.
    """
    quest = _quests.get(quest_id)
    if not quest:
        raise HTTPException(status_code=404, detail=f"Quest {quest_id} not found.")

    # Find the session (by explicit id or by quest_id lookup)
    session: QuestSession | None = None
    orchestrator: OrchestratorAgent | None = None
    if session_id:
        session = _sessions.get(session_id)
    else:
        for s in _sessions.values():
            if s.quest_id == quest_id and s.active:
                session = s
                break
    if not session:
        raise HTTPException(status_code=404, detail="No active session found for this quest.")
    orchestrator = _orchestrators.get(session.session_id)

    # Resolve the current step's activity
    current_step = None
    for step in quest.steps:
        if step.step_id == session.state.current_step:
            current_step = step
            break
    if not current_step or not current_step.activity.name:
        raise HTTPException(status_code=400, detail="Current step has no bookable activity.")

    activity = current_step.activity

    # Prepare
    intent = await prepare_booking(
        activity_name=activity.name,
        location=quest.narrative_universe.context if quest.narrative_universe else "",
        url=activity.booking_url or None,
        budget_eur=activity.price_eur,
    )

    session.events_log.append(
        OrchestratorEvent(
            type="booking.prepared",
            content=json.dumps(intent.model_dump(), ensure_ascii=False),
        )
    )

    # Complete
    result = await complete_booking(intent)

    if result.status == "completed":
        event_type = "booking.completed"
    elif result.status == "pending_human":
        event_type = "booking.pending_human"
    else:
        event_type = "booking.completed"  # failed also goes here

    booking_event = OrchestratorEvent(
        type=event_type,
        content=json.dumps(result.model_dump(), ensure_ascii=False),
    )
    session.events_log.append(booking_event)

    # Notify the orchestrator so a character can narrate the outcome
    if orchestrator:
        if result.status == "completed":
            directive = (
                f"La réservation pour '{activity.name}' est confirmée "
                f"(ref: {result.booking_ref}). Annonce-le au joueur in-character."
            )
        elif result.status == "pending_human":
            directive = (
                f"La réservation pour '{activity.name}' nécessite une action manuelle. "
                f"Dis au joueur d'aller sur {result.confirmation_url} pour finaliser."
            )
        else:
            directive = (
                f"La réservation automatique pour '{activity.name}' a échoué. "
                f"Rassure le joueur — il peut prouver sa visite autrement (photo, check-in)."
            )

        narration_events = await orchestrator.react(
            trigger="action",
            player_action=PlayerAction(type="custom", content=f"[booking:{result.status}] {directive}"),
        )
    else:
        narration_events = []

    return {
        "quest_id": quest_id,
        "session_id": session.session_id,
        "activity": activity.name,
        "intent": intent.model_dump(),
        "result": result.model_dump(),
        "narration_events": [e.model_dump() for e in narration_events],
    }


# --- Memory / completion helpers ---


async def _check_quest_completion(
    session: QuestSession, quest: QuestOutput
) -> dict | None:
    """Persist quest memory + update player profile when the quest is done.

    Returns a completion dict on success, None if not yet complete or already
    persisted.  Retry-safe: partial failures leave ``completed_at`` as None so
    the next request retries from wherever it left off.
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

        # Both steps succeeded — mark session as completed.
        session.completed_at = datetime.now().isoformat()
        session.active = False

        return {
            "quest_completed": True,
            "quest_root_hash": quest_root_hash,
            "duration_minutes": duration_min,
            "player_id": player_id,
        }
    except Exception:
        logger.exception("Quest completion persistence failed for session %s", session.session_id)
        return None


@app.get("/memory/{player_id}")
async def get_player_memory(player_id: str) -> dict:
    """Retrieve a player's persistent profile from 0G Storage."""
    profile = await load_player_profile(player_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"No profile found for player {player_id}")
    return profile.model_dump()


@app.get("/compute/status")
async def compute_status() -> dict:
    """Returns 0G Compute provider status, balance, and fallback mode."""
    from integrations.compute.compute_client import compute_client
    return await compute_client.get_status()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "OpenD&D"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

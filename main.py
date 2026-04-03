"""OpenD&D — Quest Research, Generation & Runtime API."""

from __future__ import annotations

import json
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

    # Create orchestrator
    orchestrator = OrchestratorAgent(
        quest=quest,
        session=session,
        allow_arg=request.allow_arg,
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

    return {
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

    return {
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

    return {
        "session_id": session.session_id,
        "events": [e.model_dump() for e in events],
        "state": {
            "current_step": session.state.current_step,
            "elapsed_minutes": session.state.total_elapsed_seconds // 60,
            "idle_seconds": session.state.time_since_last_event_seconds,
        },
    }


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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "OpenD&D"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

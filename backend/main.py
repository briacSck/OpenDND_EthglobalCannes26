"""OpenD&D — Quest Research, Generation & Runtime API."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel as PydanticBaseModel
from agents.city_research.models import QuestRequest as ResearchRequest, CityContext
from agents.city_research.agent import CityResearchAgent
from agents.quest_generation.models import QuestRequest, QuestOutput, Character, MemoryState
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
from agents.booking.models import BookingFormData, BookingIntent, BookingResult
from agents.memory import index as memory_index
from config import DEMO_MODE
from blockchain import blockchain_router
from agents.voice.router import router as voice_router, init_stores as init_voice_stores

import os

logger = logging.getLogger(__name__)


def _load_pregenerated_quest(request: QuestRequest) -> QuestOutput:
    """Load the pre-generated quest from checkpoints and assemble a QuestOutput."""
    import uuid as _uuid

    base = os.path.join(os.path.dirname(__file__), "pregenerated")
    concept_path = os.path.join(base, "pregenerated_concept.json")
    steps_path = os.path.join(base, "pregenerated_steps.json")

    with open(concept_path, "r", encoding="utf-8") as f:
        concept = json.load(f)
    with open(steps_path, "r", encoding="utf-8") as f:
        steps_data = json.load(f)

    # Merge concept + steps + default meta
    quest_raw = {**concept, **steps_data}

    # Add default meta fields that would normally come from phase 3
    quest_raw.setdefault("narrative_beats", [
        {"beat_id": 1, "description": "First contact with M. Critique sets the tone", "characters_involved": ["M. Critique"], "earliest_step": 1, "latest_step": 1, "tension_level": "medium", "can_be_skipped": False, "possible_triggers": ["start"]},
        {"beat_id": 2, "description": "Margot reveals her academic obsession with the critics", "characters_involved": ["Margot"], "earliest_step": 1, "latest_step": 2, "tension_level": "low", "can_be_skipped": True, "possible_triggers": ["player asks about critics"]},
        {"beat_id": 3, "description": "Underground discovery — the scope of the critics' network becomes clear", "characters_involved": ["Jean-Claude", "Margot"], "earliest_step": 2, "latest_step": 3, "tension_level": "high", "can_be_skipped": False, "possible_triggers": ["photo_sent", "gps_arrival"]},
        {"beat_id": 4, "description": "Clémentine's first contact — star ratings as communication", "characters_involved": ["Clémentine"], "earliest_step": 3, "latest_step": 4, "tension_level": "medium", "can_be_skipped": False, "possible_triggers": ["collaborative_step"]},
        {"beat_id": 5, "description": "Philippe's coffee philosophy reveals deeper truth about the critics", "characters_involved": ["Philippe"], "earliest_step": 3, "latest_step": 5, "tension_level": "medium", "can_be_skipped": True, "possible_triggers": ["player visits café", "player messages Philippe"]},
        {"beat_id": 6, "description": "M. Critique's mask slips — hints at being the founder", "characters_involved": ["M. Critique", "Jean-Claude"], "earliest_step": 4, "latest_step": 5, "tension_level": "high", "can_be_skipped": False, "possible_triggers": ["trust > 70"]},
        {"beat_id": 7, "description": "The ancient truth — rating systems predate cinema", "characters_involved": ["M. Critique", "Margot", "Philippe"], "earliest_step": 6, "latest_step": 6, "tension_level": "climax", "can_be_skipped": False, "possible_triggers": ["museum_entry"]},
    ])
    quest_raw.setdefault("resolution_principles", [
        "If player earned M. Critique's trust > 70 → he reveals himself as founder directly",
        "If player bonded with Margot → she publishes her book with player as co-author",
        "If player dismissed the critics → ending focuses on surface world victory",
        "If player embraced the critics' philosophy → invited to join as ambassador",
        "If player balanced both worlds → becomes bridge between surface and underground",
    ])
    quest_raw.setdefault("trust_dynamics", {
        "M. Critique": {"low": "Speaks only in cryptic film references, withholds key information", "medium": "Shares mission details but keeps his identity secret", "high": "Reveals himself as the founder, offers genuine mentorship"},
        "Margot": {"low": "Pure academic detachment, treats player as research subject", "medium": "Shares theories openly, hints at her book project", "high": "Confides about the book, becomes genuine ally and friend"},
        "Jean-Claude": {"low": "Gruff security guard persona, minimal help", "medium": "Shares historical anecdotes, opens some doors", "high": "Reveals he's been feeding info to critics, becomes protective"},
        "Clémentine": {"low": "Only communicates in star ratings, dismissive", "medium": "Begins using words, shows grudging respect", "high": "Reveals homesickness, drops the arrogant act"},
        "Philippe": {"low": "Polite but guarded café owner, no personal details", "medium": "Flirtatious film/coffee metaphors, shares intelligence", "high": "Reveals Hollywood past, deep emotional connection"},
    })
    quest_raw.setdefault("resolution", {
        "skill_gained": "urban exploration",
        "prize": {"xp_total": 500, "token_amount": 50},
    })

    # Build characters with basic system prompts (skip AI enrichment)
    characters = []
    for raw_char in quest_raw.get("characters", []):
        characters.append(Character(
            name=raw_char.get("name", "Unknown"),
            age=raw_char.get("age", 0),
            type=raw_char.get("type", "secondary"),
            archetype=raw_char.get("archetype", ""),
            personality=raw_char.get("personality", ""),
            speech_pattern=raw_char.get("speech_pattern", ""),
            relationship_to_player=raw_char.get("relationship_to_player", ""),
            secret=raw_char.get("secret", ""),
            evolution_rules=raw_char.get("evolution_rules", ""),
            reactions_imprevues=raw_char.get("reactions_imprevues", ""),
            voice_id="elevenlabs_placeholder",
            memory_state=MemoryState(),
            system_prompt=f"You are {raw_char.get('name', 'a character')}. {raw_char.get('personality', '')} Your speech style: {raw_char.get('speech_pattern', '')}",
        ))

    return pipeline._assemble_quest(
        raw=quest_raw,
        request=request,
        characters=characters,
        curator_iterations=0,
        judge_iterations=0,
        judge_score=85,
    )

app = FastAPI(title="OpenD&D", description="AI-powered real-life quest system")
app.include_router(blockchain_router)
app.include_router(voice_router)

# In-memory stores (replace with DB later)
_quests: dict[str, QuestOutput] = {}
_sessions: dict[str, QuestSession] = {}
_orchestrators: dict[str, OrchestratorAgent] = {}

# Share stores with voice router
init_voice_stores(_sessions, _orchestrators)


# --- Existing endpoints ---

@app.post("/research", response_model=CityContext)
async def research_city(request: ResearchRequest) -> CityContext:
    """Run the City Research Agent to gather data for a quest."""
    agent = CityResearchAgent()
    context = await agent.research(request.model_dump())
    return context


@app.post("/generate", response_model=QuestOutput)
async def generate_quest(request: QuestRequest) -> QuestOutput:
    """Return pre-generated quest instantly (no AI pipeline)."""
    quest = _load_pregenerated_quest(request)
    # Store for runtime
    _quests[quest.quest_id] = quest
    return quest


# --- Step Verification with Vision ---

class VerifyStepRequest(PydanticBaseModel):
    image_base64: str
    quest_id: str = ""
    step_id: int = 1
    camera_prompt: str = ""
    success_condition: str = ""
    player_action: str = ""
    step_title: str = ""

class VerifyStepResponse(PydanticBaseModel):
    validated: bool
    confidence: float = 0.0
    narrative_reaction: str = ""
    xp_earned: int = 0
    details: str = ""

@app.post("/verify-step", response_model=VerifyStepResponse)
async def verify_step(request: VerifyStepRequest) -> VerifyStepResponse:
    """Analyze a photo with Claude Vision to verify if a quest step is completed."""
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(
        base_url=os.getenv("ANTHROPIC_BASE_URL"),
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
        max_retries=3,
    )
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    # Strip data URL prefix if present
    img = request.image_base64
    if img.startswith("data:"):
        img = img.split(",", 1)[1] if "," in img else img

    system = """You are a quest step validator for an immersive urban adventure game.
You receive a photo taken by the player and must determine if it satisfies the step's objective.

Be GENEROUS in validation — if the photo is roughly in the right direction, validate it.
The goal is fun, not perfection. Only reject if the photo is completely unrelated (e.g. a blank wall when they should photograph a market).

Respond in JSON only:
{
  "validated": true/false,
  "confidence": 0.0-1.0,
  "narrative_reaction": "An in-character narrative response (2-3 sentences, dramatic and fun)",
  "details": "Brief explanation of what you see in the photo"
}"""

    user_content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": img,
            },
        },
        {
            "type": "text",
            "text": f"""Verify this quest step:

**Step**: {request.step_title}
**What the player should do**: {request.player_action}
**What to look for in the photo**: {request.camera_prompt}
**Success condition**: {request.success_condition}

Does this photo satisfy the step objective? Be generous — if the player made an effort and the photo is roughly relevant, validate it.""",
        },
    ]

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=1000,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        # Parse JSON
        json_str = text.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        data = json.loads(json_str)
        return VerifyStepResponse(
            validated=data.get("validated", False),
            confidence=data.get("confidence", 0.5),
            narrative_reaction=data.get("narrative_reaction", ""),
            xp_earned=15 if data.get("validated", False) else 0,
            details=data.get("details", ""),
        )
    except Exception as e:
        logger.error("Vision verification failed: %s", e)
        # Fallback: validate anyway to not block the player
        return VerifyStepResponse(
            validated=True,
            confidence=0.5,
            narrative_reaction="The image analysis encountered an issue, but your dedication is noted. Step validated!",
            xp_earned=10,
            details=f"Fallback validation: {str(e)[:100]}",
        )


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

    # Build form data from quest context
    form_data = BookingFormData(
        player_name=quest.player_name or session.player_alias,
        player_email=getattr(quest, "player_email", ""),
        datetime_str=getattr(quest, "quest_datetime", ""),
        guest_count=getattr(quest, "quest_players", 1),
        location=quest.narrative_universe.context if quest.narrative_universe else "",
    )

    # Complete
    result = await complete_booking(intent, form_data=form_data)

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

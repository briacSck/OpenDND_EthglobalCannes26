"""Player profile and quest memory models + persistence functions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from agents.memory import index as idx
from agents.memory.storage_client import download_json, upload_json
from agents.quest_generation.models import QuestOutput
from agents.quest_runtime.models import QuestSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class QuestSummary(BaseModel):
    """Lightweight summary of a completed quest, stored inside a PlayerProfile."""

    quest_id: str
    run_id: str = Field(description="Unique run identifier (session_id) for idempotency")
    root_hash: str = Field(description="0G Storage root hash of the full quest snapshot")
    grade: str = Field(default="", description="A–F grade from judge or player feedback")
    theme: str = Field(default="", description="Quest theme / tone")
    duration_minutes: int = 0
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class PlayerProfile(BaseModel):
    """Persistent player profile, stored on 0G Storage."""

    player_id: str
    display_name: str = ""
    completed_quests: list[QuestSummary] = Field(default_factory=list)
    extracted_preferences: dict = Field(
        default_factory=dict,
        description="AI-extracted preferences: preferred_themes, avg_pace, …",
    )
    total_xp: int = 0
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class QuestMemorySnapshot(BaseModel):
    """Full normalized snapshot of a completed quest run (uploaded to 0G)."""

    quest_id: str
    session_id: str
    quest_output: dict = Field(description="QuestOutput.model_dump()")
    final_state: dict = Field(description="SessionState.model_dump()")
    events_log: list[dict] = Field(default_factory=list)
    actions_log: list[dict] = Field(default_factory=list)
    conversations: dict = Field(default_factory=dict)
    completed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Persistence functions
# ---------------------------------------------------------------------------


async def save_quest_memory(quest: QuestOutput, session: QuestSession) -> str:
    """Upload a full quest-run snapshot to 0G Storage.

    Idempotent: if a snapshot for this run_id (session.session_id) already
    exists in the local index, the upload is skipped and the existing
    root_hash is returned.
    """
    run_id = session.session_id

    existing = idx.get_quest_root_hash(run_id)
    if existing is not None:
        logger.info("Quest memory for run %s already saved: %s", run_id, existing)
        return existing

    snapshot = QuestMemorySnapshot(
        quest_id=quest.quest_id,
        session_id=session.session_id,
        quest_output=quest.model_dump(),
        final_state=session.state.model_dump(),
        events_log=[e.model_dump() for e in session.events_log],
        actions_log=[a.model_dump() for a in session.actions_log],
        conversations={
            name: [entry.model_dump() for entry in entries]
            for name, entries in session.conversations.items()
        },
    )

    root_hash = await upload_json(snapshot.model_dump())
    stored_hash = idx.upsert_quest(run_id, quest.quest_id, root_hash)
    logger.info("Saved quest memory: run=%s quest=%s hash=%s", run_id, quest.quest_id, stored_hash)
    return stored_hash


async def update_player_profile(
    player_id: str,
    quest_summary: QuestSummary,
) -> str:
    """Load the player profile, append the quest summary, re-upload, update index.

    Creates a new profile if none exists.  Idempotent: if a summary with the
    same ``run_id`` is already present in the profile, the append is skipped.
    """
    profile = await load_player_profile(player_id)
    if profile is None:
        profile = PlayerProfile(player_id=player_id)

    # Idempotency: skip if this run is already recorded.
    if any(q.run_id == quest_summary.run_id for q in profile.completed_quests):
        logger.info(
            "Profile %s already contains run %s, skipping append",
            player_id,
            quest_summary.run_id,
        )
    else:
        profile.completed_quests.append(quest_summary)
        profile.total_xp += quest_summary.duration_minutes

    profile.updated_at = datetime.now(timezone.utc).isoformat()

    root_hash = await upload_json(profile.model_dump())
    idx.upsert_player(player_id, root_hash)
    logger.info("Updated player profile: %s -> %s", player_id, root_hash)
    return root_hash


async def load_player_profile(player_id: str) -> PlayerProfile | None:
    """Load a player profile from 0G Storage via the local index.

    Returns ``None`` if the player has no profile or the blob is unavailable.
    """
    root_hash = idx.get_player_root_hash(player_id)
    if root_hash is None:
        return None

    data = await download_json(root_hash)
    if data is None:
        logger.warning(
            "Player %s index -> %s but download returned None", player_id, root_hash
        )
        return None

    return PlayerProfile(**data)

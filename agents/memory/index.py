"""Local SQLite index — maps player_id / quest run_id to 0G Storage root hashes."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "memory_index.db"


def _get_connection() -> sqlite3.Connection:
    """Open (or create) the SQLite database and ensure tables exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS player_profiles (
            player_id  TEXT PRIMARY KEY,
            root_hash  TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quest_memories (
            run_id     TEXT PRIMARY KEY,
            quest_id   TEXT NOT NULL,
            root_hash  TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_quest_memories_quest_id
            ON quest_memories(quest_id);
        """
    )
    return conn


# ---- player_profiles --------------------------------------------------------


def upsert_player(player_id: str, root_hash: str) -> None:
    """Insert or update the root_hash for a player profile."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO player_profiles (player_id, root_hash, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(player_id) DO UPDATE SET root_hash = ?, updated_at = ?
            """,
            (player_id, root_hash, now, root_hash, now),
        )
        conn.commit()
    finally:
        conn.close()


def get_player_root_hash(player_id: str) -> str | None:
    """Return the current root_hash for a player, or None if not found."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT root_hash FROM player_profiles WHERE player_id = ?",
            (player_id,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


# ---- quest_memories ----------------------------------------------------------


def upsert_quest(run_id: str, quest_id: str, root_hash: str) -> str:
    """Record the root_hash for a quest run.

    Uses INSERT … ON CONFLICT DO NOTHING so re-calling with the same run_id
    is a safe no-op.  Always returns a usable root_hash — the one just inserted
    or the one already stored for this run_id.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO quest_memories (run_id, quest_id, root_hash, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(run_id) DO NOTHING
            """,
            (run_id, quest_id, root_hash, now),
        )
        conn.commit()
        # Always read back the stored value (handles both insert and no-op).
        row = conn.execute(
            "SELECT root_hash FROM quest_memories WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return row[0]  # guaranteed to exist
    finally:
        conn.close()


def get_quest_root_hash(run_id: str) -> str | None:
    """Return the root_hash for a specific quest run, or None."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT root_hash FROM quest_memories WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_quest_root_hashes_for_quest(quest_id: str) -> list[str]:
    """Return all root_hashes for every run of a given quest."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT root_hash FROM quest_memories WHERE quest_id = ? ORDER BY created_at",
            (quest_id,),
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()

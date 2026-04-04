"""Pydantic models for blockchain integration."""

from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class RewardTx(BaseModel):
    """A reward transaction record — mirrors the PRD RewardTx domain object."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    quest_run_id: str
    chain: str = "hedera"
    type: str = "hbar_transfer"
    status: str = "pending"  # pending | broadcasted | confirmed | failed
    tx_hash: str | None = None
    nft_serial: int | None = None
    amount: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StakeTx(BaseModel):
    """A stake/lock record for quest participation."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    quest_id: str
    player_account_id: str
    amount: int  # tinybars
    status: str = "locked"  # locked | won | lost
    stake_tx_hash: str | None = None
    refund_tx_hash: str | None = None
    bonus: int = 0
    nft_serial: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HCSMessage(BaseModel):
    """A Hedera Consensus Service message record."""

    topic_id: str
    sequence_number: int
    event_type: str
    payload: dict
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

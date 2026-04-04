"""Hedera reward — on-chain quest completion via blockchain/ module.

Wraps the blockchain module (real Hedera SDK) while keeping the same
interface that main.py expects: trigger_reward() → RewardTx.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from config import DEMO_MODE

logger = logging.getLogger(__name__)


class RewardTx(BaseModel):
    """On-chain reward transaction receipt."""

    tx_hash: str
    status: str = Field(default="CONFIRMED", description="CONFIRMED | FAILED | DEMO")
    chain: str = "hedera"
    quest_id: str = ""
    player_wallet: str = ""
    memory_root_hash: str = Field(
        default="", description="0G Storage root hash linking to off-chain quest memory"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


async def trigger_reward(
    quest_id: str,
    player_wallet: str,
    grade: str,
    memory_root_hash: str,
) -> RewardTx:
    """Submit on-chain proof of quest completion and return a RewardTx.

    Uses the blockchain/ module (real Hedera SDK) for:
    - HBAR reward transfer to the player
    - NFT badge mint with quest metadata
    - HCS event log with memory_root_hash as on-chain anchor

    In DEMO_MODE: returns a mock RewardTx instantly.
    """
    import hashlib
    import json

    if DEMO_MODE:
        payload = {
            "quest_id": quest_id,
            "player_wallet": player_wallet,
            "grade": grade,
            "memory_root_hash": memory_root_hash,
        }
        fake_hash = "0.0.demo-" + hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()[:16]
        logger.info("DEMO reward: %s -> %s", quest_id, fake_hash)
        return RewardTx(
            tx_hash=fake_hash,
            status="DEMO",
            quest_id=quest_id,
            player_wallet=player_wallet,
            memory_root_hash=memory_root_hash,
        )

    # Real Hedera reward via blockchain/ module
    from blockchain import reward_player, log_quest_event

    try:
        # 1. Transfer HBAR + mint NFT badge
        tx = await reward_player(
            quest_id=quest_id,
            player_account_id=player_wallet,
            token_amount=1,
            nft_metadata={
                "quest_id": quest_id,
                "grade": grade,
                "memory_root_hash": memory_root_hash,
            },
        )

        # 2. Log the memory_root_hash on HCS as on-chain anchor
        await log_quest_event(
            quest_id=quest_id,
            event_type="reward.confirmed",
            payload={
                "player": player_wallet,
                "grade": grade,
                "memory_root_hash": memory_root_hash,
                "tx_hash": tx.tx_hash,
                "nft_serial": tx.nft_serial,
            },
        )

        logger.info("Hedera reward confirmed: quest=%s tx=%s", quest_id, tx.tx_hash)
        return RewardTx(
            tx_hash=tx.tx_hash or "",
            status="CONFIRMED",
            quest_id=quest_id,
            player_wallet=player_wallet,
            memory_root_hash=memory_root_hash,
        )

    except Exception as exc:
        logger.error("Hedera reward failed: quest=%s error=%s", quest_id, exc)
        return RewardTx(
            tx_hash="",
            status="FAILED",
            quest_id=quest_id,
            player_wallet=player_wallet,
            memory_root_hash=memory_root_hash,
        )

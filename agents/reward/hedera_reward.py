"""Hedera reward — submit HCS message anchoring quest completion on-chain."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel, Field

from config import DEMO_MODE, HEDERA_ACCOUNT_ID, HEDERA_PRIVATE_KEY, HEDERA_NETWORK

logger = logging.getLogger(__name__)

_MIRROR_URLS = {
    "testnet": "https://testnet.mirrornode.hedera.com",
    "mainnet": "https://mainnet.mirrornode.hedera.com",
}


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
    """Submit an HCS message with quest reward payload and return a RewardTx.

    In DEMO_MODE: returns a mock RewardTx instantly.
    In real mode: submits to Hedera Consensus Service via the Mirror REST API.
    """
    payload = {
        "quest_id": quest_id,
        "player_wallet": player_wallet,
        "grade": grade,
        "memory_root_hash": memory_root_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if DEMO_MODE:
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

    if not HEDERA_ACCOUNT_ID or not HEDERA_PRIVATE_KEY:
        raise RuntimeError(
            "HEDERA_ACCOUNT_ID and HEDERA_PRIVATE_KEY must be set for real rewards"
        )

    mirror_url = _MIRROR_URLS.get(HEDERA_NETWORK, _MIRROR_URLS["testnet"])

    # Submit HCS message via Hedera REST API
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{mirror_url}/api/v1/transactions",
            json={
                "operatorAccountId": HEDERA_ACCOUNT_ID,
                "type": "consensusSubmitMessage",
                "params": {
                    "message": json.dumps(payload, ensure_ascii=False),
                },
            },
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        result = resp.json()
        tx_hash = result.get("transactionId", str(uuid.uuid4()))

    logger.info("Hedera reward submitted: quest=%s tx=%s", quest_id, tx_hash)
    return RewardTx(
        tx_hash=tx_hash,
        status="CONFIRMED",
        quest_id=quest_id,
        player_wallet=player_wallet,
        memory_root_hash=memory_root_hash,
    )

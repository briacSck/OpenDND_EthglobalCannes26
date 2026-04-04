"""OpenDND Blockchain — Hedera integration for quest rewards and event logging.

Public API:
    initialize_hedera()   — call once at startup
    reward_player(...)    — transfer HBAR + mint NFT badge on quest completion
    log_quest_event(...)  — submit event to HCS topic
"""

from __future__ import annotations

from .config import get_client
from .models import RewardTx
from .hts_service import transfer_hbar, mint_quest_nft
from .hcs_service import submit_event
from .x402_middleware import X402PaymentMiddleware
from .router import router as blockchain_router
from .stake_service import stake_hbar, resolve_quest


async def initialize_hedera() -> None:
    """Initialize the Hedera client. Call once at FastAPI startup."""
    get_client()


async def reward_player(
    quest_id: str,
    player_account_id: str,
    token_amount: int = 1,
    nft_metadata: dict | None = None,
) -> RewardTx:
    """Issue a quest completion reward: HBAR transfer + optional NFT badge.

    Returns a RewardTx record with tx_hash and nft_serial.
    """
    reward = RewardTx(quest_run_id=quest_id, amount=token_amount)

    try:
        # 1. Transfer HBAR reward
        tx_hash = await transfer_hbar(player_account_id, token_amount)
        reward.tx_hash = tx_hash
        reward.status = "broadcasted"

        # 2. Mint NFT badge (if metadata provided)
        if nft_metadata:
            serial = await mint_quest_nft(nft_metadata)
            reward.nft_serial = serial
            reward.type = "hbar_transfer+nft_mint"

        # 3. Log reward event to HCS
        await log_quest_event(
            quest_id=quest_id,
            event_type="reward.confirmed",
            payload={
                "player": player_account_id,
                "amount": token_amount,
                "tx_hash": reward.tx_hash,
                "nft_serial": reward.nft_serial,
            },
        )

        reward.status = "confirmed"

    except Exception as exc:
        reward.status = "failed"
        raise RuntimeError(f"Hedera reward failed: {exc}") from exc

    return reward


async def log_quest_event(
    quest_id: str,
    event_type: str,
    payload: dict,
) -> str | None:
    """Log a quest event to HCS. Returns sequence number or None if HCS is not configured."""
    import os

    topic_id = os.getenv("HEDERA_QUEST_TOPIC_ID")
    if not topic_id:
        return None

    msg = await submit_event(
        topic_id=topic_id,
        event_type=event_type,
        payload={"quest_id": quest_id, **payload},
    )
    return str(msg.sequence_number)

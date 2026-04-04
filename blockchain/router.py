"""FastAPI router exposing all blockchain endpoints.

Usage in main.py:
    from blockchain import blockchain_router
    app.include_router(blockchain_router)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/blockchain", tags=["blockchain"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class RewardRequest(BaseModel):
    quest_id: str
    player_account_id: str
    token_amount: int = 1
    nft_metadata: dict | None = None


class EventRequest(BaseModel):
    quest_id: str
    event_type: str
    payload: dict = Field(default_factory=dict)


class MintRequest(BaseModel):
    metadata: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
async def blockchain_health():
    """Check that the Hedera client is connected."""
    try:
        from . import initialize_hedera
        await initialize_hedera()
        return {"status": "ok", "network": "testnet"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/reward")
async def reward(req: RewardRequest):
    """Issue a quest completion reward: HBAR transfer + optional NFT badge + HCS log."""
    from . import reward_player

    try:
        tx = await reward_player(
            quest_id=req.quest_id,
            player_account_id=req.player_account_id,
            token_amount=req.token_amount,
            nft_metadata=req.nft_metadata,
        )
        return tx.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/events")
async def log_event(req: EventRequest):
    """Log a quest event to the Hedera Consensus Service topic."""
    from . import log_quest_event

    seq = await log_quest_event(
        quest_id=req.quest_id,
        event_type=req.event_type,
        payload=req.payload,
    )
    if seq is None:
        raise HTTPException(status_code=503, detail="HEDERA_QUEST_TOPIC_ID not configured")
    return {"sequence_number": seq, "topic_event": req.event_type}


@router.post("/nft/mint")
async def mint_nft(req: MintRequest):
    """Mint an NFT quest badge with the given metadata."""
    from .hts_service import mint_quest_nft

    try:
        serial = await mint_quest_nft(req.metadata)
        return {"serial_number": serial}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tx/{tx_id:path}")
async def verify_tx(tx_id: str):
    """Verify a Hedera transaction via the mirror node."""
    from .x402_middleware import _verify_hedera_tx

    import os
    pay_to = os.getenv("HEDERA_OPERATOR_ID", "")
    verified = await _verify_hedera_tx(tx_id, expected_to=pay_to, expected_amount=0)
    return {"tx_id": tx_id, "verified": verified}

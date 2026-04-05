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


class StakeRequest(BaseModel):
    quest_id: str
    player_account_id: str
    amount: int  # tinybars
    stake_tx_hash: str  # Hedera tx ID proving the player paid


class ResolveRequest(BaseModel):
    quest_id: str
    outcome: str = Field(description="'win' or 'lose'")
    nft_metadata: dict | None = None


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
    from .hts_service import get_or_create_hedera_account

    try:
        # If EVM address, resolve to Hedera account
        player_id = req.player_account_id
        if player_id.startswith("0x"):
            player_id, _key = await get_or_create_hedera_account(player_id)

        tx = await reward_player(
            quest_id=req.quest_id,
            player_account_id=player_id,
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


# ---------------------------------------------------------------------------
# Account creation
# ---------------------------------------------------------------------------

class CreateAccountRequest(BaseModel):
    evm_address: str


@router.post("/create-account")
async def create_account(req: CreateAccountRequest):
    """Create a Hedera testnet account for an EVM wallet address."""
    from .hts_service import get_or_create_hedera_account

    try:
        account_id, _key = await get_or_create_hedera_account(req.evm_address)
        return {"evm_address": req.evm_address, "hedera_account_id": account_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/account/{evm_address}")
async def get_account(evm_address: str):
    """Get Hedera account ID for an EVM address (creates one if needed)."""
    from .hts_service import get_or_create_hedera_account

    try:
        account_id, _key = await get_or_create_hedera_account(evm_address)
        return {"evm_address": evm_address, "hedera_account_id": account_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Stake / Lock endpoints
# ---------------------------------------------------------------------------

@router.post("/stake")
async def stake(req: StakeRequest):
    """Lock HBAR for a quest ON-CHAIN. Player → operator transfer."""
    from .stake_service import stake_hbar
    from .hts_service import get_or_create_hedera_account

    try:
        evm_address = None
        player_id = req.player_account_id

        # If EVM address, resolve to Hedera account (keeps key in memory for signing)
        if player_id.startswith("0x"):
            evm_address = player_id
            player_id, _key = await get_or_create_hedera_account(player_id)

        tx = await stake_hbar(
            quest_id=req.quest_id,
            player_account_id=player_id,
            amount=req.amount,
            stake_tx_hash=req.stake_tx_hash,
            evm_address=evm_address,
        )
        return tx.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/resolve")
async def resolve(req: ResolveRequest):
    """Resolve a quest: 'win' refunds stake + bonus + NFT, 'lose' burns the stake."""
    from .stake_service import resolve_quest

    try:
        tx = await resolve_quest(
            quest_id=req.quest_id,
            outcome=req.outcome,
            nft_metadata=req.nft_metadata,
        )
        return tx.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/stake/{quest_id}")
async def get_stake_status(quest_id: str):
    """Get the stake status for a quest."""
    from .stake_service import get_stake

    stake = get_stake(quest_id)
    if not stake:
        raise HTTPException(status_code=404, detail=f"No stake found for quest {quest_id}")
    return stake.model_dump()


@router.get("/tx/{tx_id:path}")
async def verify_tx(tx_id: str):
    """Verify a Hedera transaction via the mirror node."""
    from .x402_middleware import _verify_hedera_tx

    import os
    pay_to = os.getenv("HEDERA_OPERATOR_ID", "")
    verified = await _verify_hedera_tx(tx_id, expected_to=pay_to, expected_amount=0)
    return {"tx_id": tx_id, "verified": verified}

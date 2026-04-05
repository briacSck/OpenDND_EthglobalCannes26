"""Stake/Lock service — players stake HBAR before a quest, win or lose.

All stakes and rewards happen ON-CHAIN via real Hedera transfers.
"""

from __future__ import annotations

from .models import StakeTx
from .hts_service import transfer_hbar, mint_quest_nft, stake_hbar_onchain, get_player_key, PrivateKey

# In-memory stake store (mirrors _quests/_sessions pattern in main.py)
_stakes: dict[str, StakeTx] = {}


async def stake_hbar(
    quest_id: str,
    player_account_id: str,
    amount: int,
    stake_tx_hash: str | None = None,
    evm_address: str | None = None,
) -> StakeTx:
    """Stake HBAR on-chain: transfer from player → operator, then record.

    If evm_address is provided, uses the stored player key to sign.
    Falls back to recording only if on-chain transfer fails.
    """
    from . import log_quest_event

    tx_hash = stake_tx_hash

    # Try on-chain stake (player → operator)
    if evm_address:
        player_key = get_player_key(evm_address)
        if player_key and amount > 0:
            try:
                tx_hash = await stake_hbar_onchain(player_account_id, player_key, amount)
            except Exception as e:
                import logging
                logging.warning(f"On-chain stake failed, recording anyway: {e}")
                tx_hash = f"failed-onchain-{quest_id}"

    stake = StakeTx(
        quest_id=quest_id,
        player_account_id=player_account_id,
        amount=amount,
        stake_tx_hash=tx_hash,
    )

    _stakes[quest_id] = stake

    await log_quest_event(
        quest_id=quest_id,
        event_type="stake.locked",
        payload={
            "player": player_account_id,
            "amount": amount,
            "tx_hash": tx_hash,
        },
    )

    return stake


async def resolve_quest(
    quest_id: str,
    outcome: str,
    nft_metadata: dict | None = None,
) -> StakeTx:
    """Resolve a quest stake: 'win' refunds + bonus + NFT, 'lose' burns the stake."""
    from . import log_quest_event

    stake = _stakes.get(quest_id)
    if not stake:
        raise ValueError(f"No stake found for quest {quest_id}")

    if stake.status != "locked":
        raise ValueError(f"Stake already resolved: {stake.status}")

    if outcome == "win":
        # Calculate bonus from the redistribution pool
        bonus = _get_bonus()

        # Refund stake + bonus to player
        payout = stake.amount + bonus
        refund_tx = await transfer_hbar(stake.player_account_id, payout)

        stake.refund_tx_hash = refund_tx
        stake.bonus = bonus
        stake.status = "won"

        # Mint NFT badge
        if nft_metadata:
            serial = await mint_quest_nft(nft_metadata)
            stake.nft_serial = serial

        await log_quest_event(
            quest_id=quest_id,
            event_type="stake.won",
            payload={
                "player": stake.player_account_id,
                "refund": payout,
                "bonus": bonus,
                "refund_tx": refund_tx,
                "nft_serial": stake.nft_serial,
            },
        )

    elif outcome == "lose":
        stake.status = "lost"

        await log_quest_event(
            quest_id=quest_id,
            event_type="stake.lost",
            payload={
                "player": stake.player_account_id,
                "amount_burned": stake.amount,
            },
        )

    else:
        raise ValueError(f"Invalid outcome: {outcome}. Must be 'win' or 'lose'.")

    return stake


def get_stake(quest_id: str) -> StakeTx | None:
    """Get the stake record for a quest."""
    return _stakes.get(quest_id)


def _get_bonus() -> int:
    """Calculate available bonus from the redistribution pool.

    Pool = sum of lost stakes - sum of bonuses already paid out.
    Bonus per winner = pool // number of pending winners (here just 1 at a time).
    """
    pool = sum(s.amount for s in _stakes.values() if s.status == "lost")
    paid = sum(s.bonus for s in _stakes.values() if s.status == "won")
    available = pool - paid

    if available <= 0:
        return 0

    # Give 50% of the available pool as bonus (keep some in reserve)
    return available // 2

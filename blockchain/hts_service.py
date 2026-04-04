"""Hedera Token Service — HBAR transfers and NFT badge minting."""

from __future__ import annotations

import asyncio
import json
import os

from hiero_sdk_python import (
    AccountId,
    Hbar,
    TokenCreateTransaction,
    TokenId,
    TokenMintTransaction,
    TokenType,
    SupplyType,
    TransferTransaction,
)

from .config import get_client, get_operator_id, get_operator_key


# ---------------------------------------------------------------------------
# HBAR transfer
# ---------------------------------------------------------------------------

def _transfer_hbar_sync(to_account_id: str, amount: int) -> str:
    """Transfer HBAR (in tinybars) from operator to recipient. Returns tx hash."""
    client = get_client()
    operator_id = get_operator_id()
    operator_key = get_operator_key()
    recipient = AccountId.from_string(to_account_id)

    receipt = (
        TransferTransaction()
        .add_hbar_transfer(operator_id, Hbar(-amount))
        .add_hbar_transfer(recipient, Hbar(amount))
        .freeze_with(client)
        .sign(operator_key)
        .execute(client)
    )

    return str(getattr(receipt, "transaction_id", receipt))


async def transfer_hbar(to_account_id: str, amount: int) -> str:
    """Async wrapper — transfer HBAR to a player account."""
    return await asyncio.to_thread(_transfer_hbar_sync, to_account_id, amount)


# ---------------------------------------------------------------------------
# NFT badge minting
# ---------------------------------------------------------------------------

def _create_nft_token_class_sync() -> str:
    """One-time: create the OpenDND Quest Badge NFT token class. Returns token ID."""
    client = get_client()
    operator_id = get_operator_id()
    operator_key = get_operator_key()

    receipt = (
        TokenCreateTransaction()
        .set_token_name("OpenDND Quest Badge")
        .set_token_symbol("ODND")
        .set_decimals(0)
        .set_initial_supply(0)
        .set_token_type(TokenType.NON_FUNGIBLE_UNIQUE)
        .set_supply_type(SupplyType.FINITE)
        .set_max_supply(10_000)
        .set_treasury_account_id(operator_id)
        .set_admin_key(operator_key.public_key())
        .set_supply_key(operator_key.public_key())
        .freeze_with(client)
        .sign(operator_key)
        .execute(client)
    )

    return str(receipt.token_id)


async def create_nft_token_class() -> str:
    """Async wrapper — create NFT token class on testnet."""
    return await asyncio.to_thread(_create_nft_token_class_sync)


def _mint_quest_nft_sync(nft_metadata: dict) -> int:
    """Mint a single quest badge NFT with metadata. Returns serial number."""
    client = get_client()
    operator_key = get_operator_key()

    nft_token_id = os.environ["HEDERA_NFT_TOKEN_ID"]
    metadata_bytes = json.dumps(nft_metadata, separators=(",", ":")).encode("utf-8")

    receipt = (
        TokenMintTransaction()
        .set_token_id(TokenId.from_string(nft_token_id))
        .set_metadata(metadata_bytes)
        .freeze_with(client)
        .sign(operator_key)
        .execute(client)
    )

    serials = receipt.serial_numbers
    return serials[0] if serials else 0


async def mint_quest_nft(nft_metadata: dict) -> int:
    """Async wrapper — mint a quest badge NFT."""
    return await asyncio.to_thread(_mint_quest_nft_sync, nft_metadata)

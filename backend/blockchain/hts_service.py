"""Hedera Token Service — HBAR transfers, account creation, and NFT badge minting."""

from __future__ import annotations

import asyncio
import json
import os

from hiero_sdk_python import (
    AccountCreateTransaction,
    AccountId,
    Hbar,
    PrivateKey,
    TokenCreateTransaction,
    TokenId,
    TokenMintTransaction,
    TokenType,
    SupplyType,
    TransferTransaction,
)

from .config import get_client, get_operator_id, get_operator_key


# ---------------------------------------------------------------------------
# Account creation (for EVM wallet users who don't have a Hedera account)
# ---------------------------------------------------------------------------

# In-memory mapping of EVM address → (Hedera account ID, private key)
_evm_to_hedera: dict[str, tuple[str, str]] = {}


def _create_hedera_account_sync(initial_balance: int = 100) -> tuple[str, str]:
    """Create a new Hedera account funded by the operator. Returns (account_id, private_key_str)."""
    client = get_client()
    operator_key = get_operator_key()

    new_key = PrivateKey.generate()

    receipt = (
        AccountCreateTransaction()
        .set_key(new_key.public_key())
        .set_initial_balance(Hbar(initial_balance))
        .freeze_with(client)
        .sign(operator_key)
        .execute(client)
    )

    account_id = str(receipt.account_id)
    return account_id, new_key.to_string_raw()


async def create_hedera_account(initial_balance: int = 100) -> tuple[str, str]:
    """Async wrapper — create a new Hedera account."""
    return await asyncio.to_thread(_create_hedera_account_sync, initial_balance)


async def get_or_create_hedera_account(evm_address: str) -> tuple[str, str]:
    """Get or create a Hedera account for an EVM wallet address. Returns (account_id, private_key)."""
    if evm_address in _evm_to_hedera:
        return _evm_to_hedera[evm_address]

    account_id, private_key = await create_hedera_account(initial_balance=100)
    _evm_to_hedera[evm_address] = (account_id, private_key)
    return account_id, private_key


def get_player_key(evm_address: str) -> PrivateKey | None:
    """Get the stored private key for a player's Hedera account."""
    entry = _evm_to_hedera.get(evm_address)
    if entry:
        return PrivateKey.from_string(entry[1])
    return None


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


def _stake_hbar_onchain_sync(player_account_id: str, player_key: "PrivateKey", amount: int) -> str:
    """Transfer HBAR from player → operator (on-chain stake). Returns tx hash."""
    client = get_client()
    operator_id = get_operator_id()
    operator_key = get_operator_key()
    player_id = AccountId.from_string(player_account_id)

    receipt = (
        TransferTransaction()
        .add_hbar_transfer(player_id, Hbar(-amount))
        .add_hbar_transfer(operator_id, Hbar(amount))
        .freeze_with(client)
        .sign(player_key)
        .sign(operator_key)
        .execute(client)
    )

    return str(getattr(receipt, "transaction_id", receipt))


async def stake_hbar_onchain(player_account_id: str, player_key: "PrivateKey", amount: int) -> str:
    """Async wrapper — stake HBAR (player → operator) on-chain."""
    return await asyncio.to_thread(_stake_hbar_onchain_sync, player_account_id, player_key, amount)


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

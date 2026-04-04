"""Centralized configuration — loads .env and exposes typed constants."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_bool(val: str) -> bool:
    return val.strip().lower() in ("true", "1", "yes")


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required env var: {name}. "
            "Check your .env file (see .env.example for the full list)."
        )
    return value


# ---------------------------------------------------------------------------
# Demo mode (loaded first — gates which secrets are required)
# ---------------------------------------------------------------------------

DEMO_MODE: bool = _parse_bool(os.getenv("DEMO_MODE", "false"))

# ---------------------------------------------------------------------------
# Anthropic (always required)
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY: str = _require("ANTHROPIC_API_KEY")

# ---------------------------------------------------------------------------
# 0G
# ---------------------------------------------------------------------------

RPC_URL: str = os.getenv("RPC_URL", "https://evmrpc-testnet.0g.ai")
STORAGE_INDEXER: str = os.getenv("STORAGE_INDEXER", "https://indexer-storage-testnet-turbo.0g.ai")
ZG_BALANCE_THRESHOLD: str = os.getenv("ZG_BALANCE_THRESHOLD", "0.01")

if DEMO_MODE:
    PRIVATE_KEY: str | None = os.getenv("PRIVATE_KEY") or None
    PROVIDER_ADDRESS: str | None = os.getenv("PROVIDER_ADDRESS") or None
else:
    PRIVATE_KEY: str | None = _require("PRIVATE_KEY")
    PROVIDER_ADDRESS: str | None = _require("PROVIDER_ADDRESS")

# ---------------------------------------------------------------------------
# Hedera
# ---------------------------------------------------------------------------

HEDERA_NETWORK: str = os.getenv("HEDERA_NETWORK", "testnet")

if DEMO_MODE:
    HEDERA_ACCOUNT_ID: str | None = os.getenv("HEDERA_ACCOUNT_ID") or None
    HEDERA_PRIVATE_KEY: str | None = os.getenv("HEDERA_PRIVATE_KEY") or None
else:
    HEDERA_ACCOUNT_ID: str | None = _require("HEDERA_ACCOUNT_ID")
    HEDERA_PRIVATE_KEY: str | None = _require("HEDERA_PRIVATE_KEY")

# ---------------------------------------------------------------------------
# WhatsApp Business
# ---------------------------------------------------------------------------

if DEMO_MODE:
    WHATSAPP_TOKEN: str | None = os.getenv("WHATSAPP_TOKEN") or None
    WHATSAPP_PHONE_ID: str | None = os.getenv("WHATSAPP_PHONE_ID") or None
    WHATSAPP_VERIFY_TOKEN: str | None = os.getenv("WHATSAPP_VERIFY_TOKEN") or None
else:
    WHATSAPP_TOKEN: str | None = _require("WHATSAPP_TOKEN")
    WHATSAPP_PHONE_ID: str | None = _require("WHATSAPP_PHONE_ID")
    WHATSAPP_VERIFY_TOKEN: str | None = _require("WHATSAPP_VERIFY_TOKEN")

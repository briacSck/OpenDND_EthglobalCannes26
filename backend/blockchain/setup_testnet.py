#!/usr/bin/env python3
"""One-time testnet setup: create NFT token class + HCS topic.

Run once, then copy the printed IDs into your .env file.

Usage:
    cd blockchain
    uv run python setup_testnet.py
"""

import asyncio
import sys
import os

# Ensure the parent dir is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blockchain.hts_service import create_nft_token_class
from blockchain.hcs_service import create_topic


async def main() -> None:
    print("=== OpenDND Hedera Testnet Setup ===\n")

    print("1. Creating NFT token class (OpenDND Quest Badge)...")
    nft_token_id = await create_nft_token_class()
    print(f"   NFT Token ID: {nft_token_id}")

    print("\n2. Creating HCS topic (Quest Events)...")
    topic_id = await create_topic()
    print(f"   Topic ID: {topic_id}")

    print("\n=== Add these to your .env ===")
    print(f"HEDERA_NFT_TOKEN_ID={nft_token_id}")
    print(f"HEDERA_QUEST_TOPIC_ID={topic_id}")
    print("\nDone! Verify on https://hashscan.io/testnet")


if __name__ == "__main__":
    asyncio.run(main())

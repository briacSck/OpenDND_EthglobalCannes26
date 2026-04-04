"""0G Storage REST API client — upload/download JSON blobs via the indexer."""

from __future__ import annotations

import hashlib
import json
import logging

import httpx

from config import DEMO_MODE, STORAGE_INDEXER

logger = logging.getLogger(__name__)

# In-memory mock store for DEMO_MODE (volatile — lost on restart).
_demo_store: dict[str, bytes] = {}


async def upload_json(data: dict) -> str:
    """Serialize *data* to JSON, upload to 0G Storage, return the root_hash.

    In DEMO_MODE: stores in ``_demo_store`` keyed by a deterministic SHA-256
    hash so re-uploading identical data yields the same key.
    """
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")

    if DEMO_MODE:
        fake_hash = "0x" + hashlib.sha256(raw).hexdigest()
        _demo_store[fake_hash] = raw
        logger.info("DEMO upload: %d bytes -> %s", len(raw), fake_hash)
        return fake_hash

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{STORAGE_INDEXER}/file",
            content=raw,
            headers={"Content-Type": "application/octet-stream"},
        )
        resp.raise_for_status()
        result = resp.json()
        root_hash: str | None = result.get("root") or result.get("rootHash")
        if not root_hash:
            raise ValueError(f"No root hash in 0G indexer response: {result}")
        logger.info("0G upload: %d bytes -> %s", len(raw), root_hash)
        return root_hash


async def download_json(root_hash: str) -> dict | None:
    """Download a JSON blob by *root_hash* from 0G Storage and deserialize.

    Returns ``None`` if the root_hash is not found.
    In DEMO_MODE: reads from ``_demo_store``.
    """
    if DEMO_MODE:
        raw = _demo_store.get(root_hash)
        if raw is None:
            logger.warning("DEMO download: %s not found", root_hash)
            return None
        return json.loads(raw)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{STORAGE_INDEXER}/file/{root_hash}")
        if resp.status_code == 404:
            logger.warning("0G download: %s not found (404)", root_hash)
            return None
        resp.raise_for_status()
        return resp.json()

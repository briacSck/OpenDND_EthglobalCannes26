"""Hedera Consensus Service — immutable quest event logging."""

from __future__ import annotations

import asyncio
import json

from hiero_sdk_python import (
    TopicCreateTransaction,
    TopicId,
    TopicMessageSubmitTransaction,
)

from .config import get_client, get_operator_id, get_operator_key
from .models import HCSMessage


# ---------------------------------------------------------------------------
# Topic creation (one-time setup)
# ---------------------------------------------------------------------------

def _create_topic_sync(memo: str = "OpenDND Quest Events") -> str:
    """Create an HCS topic for quest event logging. Returns topic ID."""
    client = get_client()
    operator_key = get_operator_key()

    receipt = (
        TopicCreateTransaction()
        .set_memo(memo)
        .set_admin_key(operator_key.public_key())
        .freeze_with(client)
        .sign(operator_key)
        .execute(client)
    )

    return str(receipt.topic_id)


async def create_topic(memo: str = "OpenDND Quest Events") -> str:
    """Async wrapper — create HCS topic."""
    return await asyncio.to_thread(_create_topic_sync, memo)


# ---------------------------------------------------------------------------
# Event submission
# ---------------------------------------------------------------------------

def _submit_event_sync(topic_id: str, event_type: str, payload: dict) -> HCSMessage:
    """Submit a quest event to an HCS topic. Returns HCSMessage with sequence number."""
    client = get_client()
    operator_key = get_operator_key()

    message_data = json.dumps(
        {"event_type": event_type, **payload},
        separators=(",", ":"),
    )

    receipt = (
        TopicMessageSubmitTransaction()
        .set_topic_id(TopicId.from_string(topic_id))
        .set_message(message_data)
        .freeze_with(client)
        .sign(operator_key)
        .execute(client)
    )

    return HCSMessage(
        topic_id=topic_id,
        sequence_number=getattr(receipt, "topic_sequence_number", 0),
        event_type=event_type,
        payload=payload,
    )


async def submit_event(topic_id: str, event_type: str, payload: dict) -> HCSMessage:
    """Async wrapper — submit event to HCS topic."""
    return await asyncio.to_thread(_submit_event_sync, topic_id, event_type, payload)

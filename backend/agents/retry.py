"""Retry helper for Anthropic API calls with exponential backoff."""

from __future__ import annotations

import asyncio
import logging
from functools import wraps
from anthropic import RateLimitError

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
BASE_DELAY = 15  # seconds


def retry_on_rate_limit(func):
    """Decorator that retries async functions on Anthropic 429 rate limit errors."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        for attempt in range(MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except RateLimitError as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                delay = BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Rate limited (attempt %d/%d), retrying in %ds: %s",
                    attempt + 1, MAX_RETRIES, delay, str(e)[:100]
                )
                await asyncio.sleep(delay)
        return await func(*args, **kwargs)

    return wrapper

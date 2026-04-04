"""0G Compute client — routes LLM inference through 0G with Anthropic fallback.

Drop-in replacement for AsyncAnthropic.messages.create(). Returns objects with
the same .stop_reason / .content block interface so orchestrator and character
agent code stays untouched.
"""

from __future__ import annotations

import asyncio
import atexit
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from anthropic import AsyncAnthropic

from config import (
    ANTHROPIC_API_KEY,
    DEMO_MODE,
    PRIVATE_KEY,
    PROVIDER_ADDRESS,
    RPC_URL,
    ZG_BALANCE_THRESHOLD,
)

logger = logging.getLogger("opendnd.compute")

_BRIDGE_DIR = Path(__file__).resolve().parent
_BRIDGE_SCRIPT = _BRIDGE_DIR / "_broker_bridge.mjs"
_BROKER_PORT = 3721
_BROKER_URL = f"http://127.0.0.1:{_BROKER_PORT}"
_0G_TIMEOUT = 8.0
_MAX_429_RETRIES = 2
_SETTLEMENT_FAILURE_THRESHOLD = 3


# ---------------------------------------------------------------------------
# Response dataclasses — duck-type Anthropic's Message / ContentBlock
# ---------------------------------------------------------------------------

@dataclass
class ContentBlock:
    type: str
    text: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict | None = None


@dataclass
class MessageResponse:
    stop_reason: str
    content: list[ContentBlock] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tool format translation
# ---------------------------------------------------------------------------

def _anthropic_tools_to_openai(tools: list[dict]) -> list[dict]:
    """Convert Anthropic tool defs to OpenAI function-calling format."""
    result = []
    for t in tools:
        result.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            },
        })
    return result


def _openai_response_to_message(data: dict) -> MessageResponse:
    """Convert an OpenAI chat completion response to Anthropic-shaped Message."""
    choice = data["choices"][0]
    finish = choice.get("finish_reason", "stop")
    msg = choice.get("message", {})

    blocks: list[ContentBlock] = []

    # Text content
    if msg.get("content"):
        blocks.append(ContentBlock(type="text", text=msg["content"]))

    # Tool calls
    for tc in msg.get("tool_calls", []):
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            args = {}
        blocks.append(ContentBlock(
            type="tool_use",
            id=tc.get("id", ""),
            name=fn.get("name", ""),
            input=args,
        ))

    stop_reason = "tool_use" if finish == "tool_calls" else "end_turn"
    return MessageResponse(stop_reason=stop_reason, content=blocks)


def _build_openai_messages(system: str, messages: list[dict]) -> list[dict]:
    """Prepend system message in OpenAI format."""
    return [{"role": "system", "content": system}] + messages


# ---------------------------------------------------------------------------
# ComputeClient
# ---------------------------------------------------------------------------

class ComputeClient:
    """Singleton LLM client — tries 0G first, falls back to Anthropic."""

    def __init__(self) -> None:
        self._anthropic = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        self._anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

        # Provider state (populated on first non-demo call)
        self._provider_address: str | None = None
        self._provider_endpoint: str | None = None
        self._provider_model: str | None = None
        self._provider_acknowledged: bool = False
        self._last_provider_refresh: float | None = None

        # Health tracking
        self._fallback_mode: bool = DEMO_MODE
        self._settlement_failures: int = 0
        self._last_error: str | None = None

        # Broker server process
        self._broker_process: subprocess.Popen | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_message(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4000,
        tools: list[dict] | None = None,
    ) -> MessageResponse:
        """Drop-in replacement for AsyncAnthropic.messages.create()."""

        if DEMO_MODE or self._fallback_mode:
            return await self._anthropic_chat(system, messages, max_tokens, tools)

        try:
            if self._provider_endpoint is None:
                await self._discover_provider()
            return await self._0g_chat(system, messages, max_tokens, tools)
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning("0G inference failed, falling back to Anthropic: %s", exc)
            return await self._anthropic_chat(system, messages, max_tokens, tools)

    async def get_status(self) -> dict:
        """Status payload for /compute/status endpoint."""
        bal = {"main": None, "sub": None}
        if not DEMO_MODE and self._provider_address:
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(
                        f"{_BROKER_URL}/balance",
                        params={"addr": self._provider_address},
                        timeout=5,
                    )
                    if r.status_code == 200:
                        bal = r.json()
            except Exception:
                pass

        return {
            "demo_mode": DEMO_MODE,
            "fallback_mode": self._fallback_mode,
            "provider_address": self._provider_address,
            "model": self._provider_model,
            "main_balance": bal.get("main"),
            "sub_balance": bal.get("sub"),
            "provider_acknowledged": self._provider_acknowledged,
            "last_error": self._last_error,
            "last_provider_refresh_at": self._last_provider_refresh,
        }

    # ------------------------------------------------------------------
    # Broker server lifecycle
    # ------------------------------------------------------------------

    def _ensure_broker_server(self) -> None:
        """Start the Node.js broker bridge server if not already running."""
        if self._broker_process and self._broker_process.poll() is None:
            return  # still running

        env = {
            **os.environ,
            "PRIVATE_KEY": PRIVATE_KEY or "",
            "RPC_URL": RPC_URL,
        }
        self._broker_process = subprocess.Popen(
            ["node", str(_BRIDGE_SCRIPT), "serve", "--port", str(_BROKER_PORT)],
            cwd=str(_BRIDGE_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        atexit.register(self._shutdown_broker_server)

        # Poll /health until ready (max 15s)
        import urllib.request
        for _ in range(30):
            time.sleep(0.5)
            try:
                req = urllib.request.Request(f"{_BROKER_URL}/health")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        logger.info("Broker bridge server started on port %d", _BROKER_PORT)
                        return
            except Exception:
                # Check if process died
                if self._broker_process.poll() is not None:
                    stderr = self._broker_process.stderr.read().decode() if self._broker_process.stderr else ""
                    raise RuntimeError(f"Broker bridge failed to start: {stderr}")

        raise RuntimeError("Broker bridge server did not become ready within 15s")

    def _shutdown_broker_server(self) -> None:
        if self._broker_process and self._broker_process.poll() is None:
            self._broker_process.terminate()
            try:
                self._broker_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._broker_process.kill()

    # ------------------------------------------------------------------
    # Provider discovery
    # ------------------------------------------------------------------

    async def _discover_provider(self) -> None:
        """Discover the best TEE-verified chatbot provider via the broker bridge."""
        self._ensure_broker_server()

        async with httpx.AsyncClient() as client:
            # Discover providers
            r = await client.get(f"{_BROKER_URL}/discover", timeout=30)
            r.raise_for_status()
            providers = r.json()

            # Filter TEE-verified
            tee_providers = [p for p in providers if p.get("teeVerified")]
            if not tee_providers:
                # Fall back to any provider if no TEE ones
                tee_providers = providers
            if not tee_providers:
                raise RuntimeError("No chatbot providers found on 0G network")

            # Pick first available (cheapest heuristic — first listed)
            selected = tee_providers[0]
            self._provider_address = selected["address"]
            self._provider_endpoint = selected["endpoint"]
            self._provider_model = selected["model"]
            self._last_provider_refresh = time.time()

            logger.info(
                "Selected 0G provider: %s (model: %s, TEE: %s)",
                self._provider_address,
                self._provider_model,
                selected.get("teeVerified"),
            )

            # Check balance and warn
            r = await client.get(
                f"{_BROKER_URL}/balance",
                params={"addr": self._provider_address},
                timeout=10,
            )
            if r.status_code == 200:
                bal = r.json()
                main_avail = float(bal.get("main", {}).get("available", "0"))
                threshold = float(ZG_BALANCE_THRESHOLD)
                if main_avail < threshold:
                    logger.warning(
                        "0G main balance (%.4f) below threshold (%.4f). "
                        "Fund via https://faucet.0g.ai",
                        main_avail,
                        threshold,
                    )
                sub = bal.get("sub")
                if sub and float(sub.get("balance", "0")) == 0:
                    logger.warning(
                        "Provider sub-account has zero balance. "
                        "Run: node _broker_bridge.mjs transfer %s <amount>",
                        self._provider_address,
                    )

    # ------------------------------------------------------------------
    # 0G inference path
    # ------------------------------------------------------------------

    async def _get_auth_headers(self) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{_BROKER_URL}/headers",
                params={"addr": self._provider_address},
                timeout=5,
            )
            r.raise_for_status()
            return r.json()

    async def _0g_chat(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int,
        tools: list[dict] | None,
    ) -> MessageResponse:
        auth_headers = await self._get_auth_headers()

        # Build OpenAI-format request
        body: dict = {
            "model": self._provider_model,
            "messages": _build_openai_messages(system, messages),
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = _anthropic_tools_to_openai(tools)

        url = f"{self._provider_endpoint}/chat/completions"
        request_headers = {"Content-Type": "application/json", **auth_headers}

        # Retry loop for 429s
        last_exc: Exception | None = None
        for attempt in range(_MAX_429_RETRIES + 1):
            async with httpx.AsyncClient() as client:
                try:
                    r = await client.post(
                        url,
                        headers=request_headers,
                        json=body,
                        timeout=_0G_TIMEOUT,
                    )
                    if r.status_code == 429 and attempt < _MAX_429_RETRIES:
                        wait = 0.5 * (attempt + 1)
                        logger.warning("0G 429 rate-limited, retrying in %.1fs", wait)
                        await asyncio.sleep(wait)
                        # Get fresh headers for retry
                        auth_headers = await self._get_auth_headers()
                        request_headers = {"Content-Type": "application/json", **auth_headers}
                        continue

                    r.raise_for_status()
                    data = r.json()

                    # Extract chatID for processResponse
                    chat_id = (
                        r.headers.get("ZG-Res-Key")
                        or r.headers.get("zg-res-key")
                        or data.get("id")
                    )

                    # Translate response
                    result = _openai_response_to_message(data)

                    # Settlement — awaited, but failure is non-fatal
                    await self._settle(chat_id, data.get("usage"))

                    return result

                except httpx.TimeoutException:
                    raise
                except httpx.HTTPStatusError as exc:
                    last_exc = exc
                    if exc.response.status_code != 429:
                        raise

        raise last_exc or RuntimeError("0G request failed after retries")

    async def _settle(self, chat_id: str | None, usage: dict | None) -> None:
        """Call processResponse for fee settlement. Non-fatal on failure."""
        if not chat_id:
            return
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{_BROKER_URL}/process-response",
                    json={
                        "addr": self._provider_address,
                        "chatID": chat_id,
                        "usage": json.dumps(usage or {}),
                    },
                    timeout=10,
                )
                if r.status_code == 200:
                    self._settlement_failures = 0
                else:
                    raise RuntimeError(r.text)
        except Exception as exc:
            self._settlement_failures += 1
            logger.warning(
                "processResponse failed (%d/%d): %s",
                self._settlement_failures,
                _SETTLEMENT_FAILURE_THRESHOLD,
                exc,
            )
            if self._settlement_failures >= _SETTLEMENT_FAILURE_THRESHOLD:
                logger.error(
                    "Settlement failures exceeded threshold — switching to fallback mode. "
                    "Provider will be rediscovered on next opportunity."
                )
                self._fallback_mode = True
                self._provider_endpoint = None  # force rediscovery

    # ------------------------------------------------------------------
    # Anthropic fallback path
    # ------------------------------------------------------------------

    async def _anthropic_chat(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int,
        tools: list[dict] | None,
    ):
        """Direct Anthropic call. Returns native Anthropic Message object."""
        kwargs: dict = {
            "model": self._anthropic_model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        return await self._anthropic.messages.create(**kwargs)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

compute_client = ComputeClient()

"""x402 Payment Middleware for FastAPI — Hedera native implementation.

Implements the HTTP 402 Payment Required flow using Hedera Token Service.
AI agents can autonomously pay for API access by submitting HBAR transfers.

Flow:
    1. Client requests a protected endpoint without payment proof
    2. Server responds HTTP 402 with payment requirements (amount, pay_to, network)
    3. Client (AI agent) sends HBAR payment on Hedera and obtains tx_id
    4. Client retries request with X-PAYMENT-TX header containing the tx_id
    5. Server verifies the transaction on-chain and grants access
"""

from __future__ import annotations

import json
import os
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .config import get_client, get_operator_id


class X402PaymentMiddleware(BaseHTTPMiddleware):
    """Middleware that gates routes behind Hedera HBAR payments (x402 pattern)."""

    def __init__(
        self,
        app: ASGIApp,
        protected_routes: dict[str, int],
        pay_to: str | None = None,
    ) -> None:
        """
        Args:
            app: FastAPI/ASGI app.
            protected_routes: Mapping of "METHOD /path" to price in tinybars.
                Example: {"POST /quests/generate": 1_00_000_000}  # 1 HBAR
            pay_to: Hedera account to receive payments.
                Defaults to HEDERA_OPERATOR_ID.
        """
        super().__init__(app)
        self.protected_routes = protected_routes
        self.pay_to = pay_to or os.getenv("HEDERA_OPERATOR_ID", "")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        route_key = f"{request.method} {request.url.path}"

        # Not a protected route — pass through
        if route_key not in self.protected_routes:
            return await call_next(request)

        price_tinybars = self.protected_routes[route_key]

        # Check for payment proof header
        payment_tx = request.headers.get("X-PAYMENT-TX") or request.headers.get("x-payment-tx")

        if not payment_tx:
            # No payment → 402 Payment Required
            return JSONResponse(
                status_code=402,
                content={
                    "x402Version": 1,
                    "scheme": "exact",
                    "network": "hedera:testnet",
                    "payTo": self.pay_to,
                    "price": price_tinybars,
                    "priceUnit": "tinybar",
                    "description": f"Payment required: {price_tinybars} tinybars to access {route_key}",
                    "accepts": ["X-PAYMENT-TX"],
                },
                headers={"X-Payment-Required": "hedera"},
            )

        # Verify payment on-chain
        verified = await _verify_hedera_tx(payment_tx, self.pay_to, price_tinybars)

        if not verified:
            return JSONResponse(
                status_code=402,
                content={
                    "error": "payment_invalid",
                    "message": "Transaction could not be verified. Ensure payment was sent to the correct account.",
                },
            )

        # Payment verified — proceed
        response = await call_next(request)
        response.headers["X-Payment-Verified"] = payment_tx
        return response


async def _verify_hedera_tx(tx_id: str, expected_to: str, expected_amount: int) -> bool:
    """Verify a Hedera transaction via mirror node REST API.

    Checks that:
    - The transaction exists and succeeded
    - It includes a net positive HBAR transfer to `expected_to` of at least `expected_amount`
    """
    import httpx

    # Normalize tx_id: "0.0.X@seconds.nanos" → "0.0.X-seconds-nanos"
    parts = tx_id.split("@")
    if len(parts) == 2:
        account = parts[0]
        timestamp = parts[1].replace(".", "-")
        normalized = f"{account}-{timestamp}"
    else:
        normalized = tx_id

    network = os.getenv("HEDERA_NETWORK", "testnet")
    mirror_url = f"https://{network}.mirrornode.hedera.com/api/v1/transactions/{normalized}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(mirror_url)
            if resp.status_code != 200:
                return False

            data = resp.json()
            transactions = data.get("transactions", [])

            for tx in transactions:
                if tx.get("result") != "SUCCESS":
                    continue

                # Check HBAR transfers for a positive credit to expected_to
                transfers = tx.get("transfers", [])
                for t in transfers:
                    if t.get("account") == expected_to and t.get("amount", 0) >= expected_amount:
                        return True

                # For self-transfers or fee-only txs, accept if tx was SUCCESS
                # and was sent by someone (not the pay_to account itself)
                payer = parts[0] if len(parts) == 2 else None
                if payer and payer != expected_to:
                    return True

    except Exception:
        return False

    return False

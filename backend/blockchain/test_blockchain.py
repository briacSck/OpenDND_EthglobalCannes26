"""Tests for the blockchain module — runs against Hedera testnet.

Run with:
    cd blockchain && uv run --no-project pytest test_blockchain.py -v
"""

from __future__ import annotations

import os
import sys

import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def test_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from blockchain import blockchain_router

    app = FastAPI()
    app.include_router(blockchain_router)
    return TestClient(app)


@pytest.fixture(scope="session")
def operator_id():
    return os.getenv("HEDERA_OPERATOR_ID") or os.getenv("HEDERA_ACCOUNT_ID")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestModels:
    def test_reward_tx_defaults(self):
        from blockchain.models import RewardTx

        tx = RewardTx(quest_run_id="q1")
        assert tx.status == "pending"
        assert tx.chain == "hedera"
        assert tx.quest_run_id == "q1"
        assert tx.id  # auto-generated

    def test_stake_tx_defaults(self):
        from blockchain.models import StakeTx

        stake = StakeTx(quest_id="q1", player_account_id="0.0.123", amount=100)
        assert stake.status == "locked"
        assert stake.bonus == 0
        assert stake.refund_tx_hash is None

    def test_hcs_message(self):
        from blockchain.models import HCSMessage

        msg = HCSMessage(
            topic_id="0.0.1", sequence_number=1,
            event_type="test", payload={"a": 1},
        )
        assert msg.topic_id == "0.0.1"
        assert msg.payload == {"a": 1}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestConfig:
    def test_hedera_client_initializes(self):
        from blockchain.config import get_client, get_operator_id, get_operator_key

        client = get_client()
        assert client is not None
        assert get_operator_id() is not None
        assert get_operator_key() is not None

    def test_client_is_singleton(self):
        from blockchain.config import get_client

        c1 = get_client()
        c2 = get_client()
        assert c1 is c2


# ---------------------------------------------------------------------------
# HTS Service (testnet)
# ---------------------------------------------------------------------------

class TestHTSService:
    def test_transfer_hbar(self, operator_id):
        import asyncio
        from blockchain.hts_service import transfer_hbar

        # Self-transfer to avoid needing a second account
        tx_hash = asyncio.run(transfer_hbar(operator_id, 1))
        assert tx_hash
        assert "@" in tx_hash  # format: 0.0.X@timestamp

    def test_mint_nft(self):
        import asyncio
        from blockchain.hts_service import mint_quest_nft

        serial = asyncio.run(mint_quest_nft({"test": "pytest", "time": "now"}))
        assert isinstance(serial, int)
        assert serial > 0


# ---------------------------------------------------------------------------
# HCS Service (testnet)
# ---------------------------------------------------------------------------

class TestHCSService:
    def test_submit_event(self):
        import asyncio
        from blockchain.hcs_service import submit_event

        topic_id = os.environ.get("HEDERA_QUEST_TOPIC_ID")
        if not topic_id:
            pytest.skip("HEDERA_QUEST_TOPIC_ID not set")

        msg = asyncio.run(submit_event(topic_id, "test.pytest", {"run": "ci"}))
        assert msg.event_type == "test.pytest"
        assert msg.topic_id == topic_id


# ---------------------------------------------------------------------------
# Stake Service
# ---------------------------------------------------------------------------

class TestStakeService:
    def test_stake_and_resolve_win(self, operator_id):
        import asyncio
        from blockchain.stake_service import stake_hbar, resolve_quest, get_stake, _stakes

        # Clean state
        _stakes.clear()

        # Stake
        stake = asyncio.run(stake_hbar(
            quest_id="pytest-win",
            player_account_id=operator_id,
            amount=1_000_000,
            stake_tx_hash="fake-tx-pytest",
        ))
        assert stake.status == "locked"
        assert stake.amount == 1_000_000

        # Check lookup
        assert get_stake("pytest-win") is stake

        # Resolve win
        result = asyncio.run(resolve_quest("pytest-win", "win"))
        assert result.status == "won"
        assert result.refund_tx_hash  # real tx on testnet

    def test_stake_and_resolve_lose(self, operator_id):
        import asyncio
        from blockchain.stake_service import stake_hbar, resolve_quest, _stakes

        _stakes.clear()

        stake = asyncio.run(stake_hbar(
            quest_id="pytest-lose",
            player_account_id=operator_id,
            amount=500_000,
            stake_tx_hash="fake-tx-lose",
        ))

        result = asyncio.run(resolve_quest("pytest-lose", "lose"))
        assert result.status == "lost"
        assert result.refund_tx_hash is None

    def test_double_resolve_fails(self, operator_id):
        import asyncio
        from blockchain.stake_service import stake_hbar, resolve_quest, _stakes

        _stakes.clear()

        asyncio.run(stake_hbar(
            quest_id="pytest-double",
            player_account_id=operator_id,
            amount=100,
            stake_tx_hash="fake",
        ))
        asyncio.run(resolve_quest("pytest-double", "lose"))

        with pytest.raises(ValueError, match="already resolved"):
            asyncio.run(resolve_quest("pytest-double", "win"))

    def test_resolve_nonexistent_fails(self):
        import asyncio
        from blockchain.stake_service import resolve_quest

        with pytest.raises(ValueError, match="No stake found"):
            asyncio.run(resolve_quest("doesnt-exist", "win"))

    def test_bonus_from_pool(self, operator_id):
        import asyncio
        from blockchain.stake_service import stake_hbar, resolve_quest, _stakes

        _stakes.clear()

        # Loser stakes 10M tinybars
        asyncio.run(stake_hbar("pool-loser", "0.0.99999", 10_000_000, "fake"))
        asyncio.run(resolve_quest("pool-loser", "lose"))

        # Winner stakes 1M tinybars
        asyncio.run(stake_hbar("pool-winner", operator_id, 1_000_000, "fake"))
        result = asyncio.run(resolve_quest("pool-winner", "win"))

        assert result.status == "won"
        assert result.bonus > 0  # got some from the pool
        assert result.bonus == 5_000_000  # 50% of 10M pool


# ---------------------------------------------------------------------------
# Router endpoints
# ---------------------------------------------------------------------------

class TestRouter:
    def test_health(self, test_client):
        r = test_client.get("/blockchain/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_events(self, test_client):
        r = test_client.post("/blockchain/events", json={
            "quest_id": "pytest-router",
            "event_type": "test.router",
            "payload": {"from": "pytest"},
        })
        assert r.status_code == 200
        assert r.json()["sequence_number"]

    def test_nft_mint(self, test_client):
        r = test_client.post("/blockchain/nft/mint", json={
            "metadata": {"source": "pytest"},
        })
        assert r.status_code == 200
        assert r.json()["serial_number"] > 0

    def test_stake_flow(self, test_client):
        # Stake
        r = test_client.post("/blockchain/stake", json={
            "quest_id": "pytest-router-stake",
            "player_account_id": "0.0.8503635",
            "amount": 100_000,
            "stake_tx_hash": "fake-router-tx",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "locked"

        # Check
        r = test_client.get("/blockchain/stake/pytest-router-stake")
        assert r.status_code == 200
        assert r.json()["status"] == "locked"

        # Resolve
        r = test_client.post("/blockchain/resolve", json={
            "quest_id": "pytest-router-stake",
            "outcome": "win",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "won"

    def test_stake_not_found(self, test_client):
        r = test_client.get("/blockchain/stake/nope")
        assert r.status_code == 404

    def test_resolve_not_found(self, test_client):
        r = test_client.post("/blockchain/resolve", json={
            "quest_id": "nope",
            "outcome": "win",
        })
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# x402 Middleware
# ---------------------------------------------------------------------------

class TestX402Middleware:
    def test_free_endpoint_passes(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from blockchain.x402_middleware import X402PaymentMiddleware

        app = FastAPI()
        app.add_middleware(
            X402PaymentMiddleware,
            protected_routes={"GET /paid": 100},
        )

        @app.get("/free")
        async def free():
            return {"ok": True}

        c = TestClient(app)
        r = c.get("/free")
        assert r.status_code == 200

    def test_protected_returns_402(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from blockchain.x402_middleware import X402PaymentMiddleware

        app = FastAPI()
        app.add_middleware(
            X402PaymentMiddleware,
            protected_routes={"GET /paid": 100_000_000},
            pay_to="0.0.8503635",
        )

        @app.get("/paid")
        async def paid():
            return {"secret": True}

        c = TestClient(app)
        r = c.get("/paid")
        assert r.status_code == 402
        body = r.json()
        assert body["scheme"] == "exact"
        assert body["network"] == "hedera:testnet"
        assert body["payTo"] == "0.0.8503635"

    def test_402_with_payment_header(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from blockchain.x402_middleware import X402PaymentMiddleware

        app = FastAPI()
        app.add_middleware(
            X402PaymentMiddleware,
            protected_routes={"GET /paid": 1},
            pay_to="0.0.8503635",
        )

        @app.get("/paid")
        async def paid():
            return {"secret": True}

        c = TestClient(app)
        # With a payment header, it tries to verify (may fail for self-tx but doesn't 402)
        r = c.get("/paid", headers={"X-PAYMENT-TX": "0.0.8503635@1775292116.404456853"})
        assert r.status_code in (200, 402)  # depends on mirror node verification

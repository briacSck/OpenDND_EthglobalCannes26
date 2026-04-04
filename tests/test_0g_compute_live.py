"""Live integration tests for 0G Compute — requires real credentials + funded wallet.

Run with:
    cd backend && python -m pytest ../tests/test_0g_compute_live.py -v -s

Skip conditions:
    - DEMO_MODE=true (default) → all tests skipped
    - No PRIVATE_KEY → skipped
    - Broker bridge unreachable → individual test failures (not skip)

These tests hit the real 0G testnet. They cost real (testnet) tokens.
Timeouts are generous (60s) because testnet latency varies.
"""

import os
import sys

# --- Path setup (tests/ is sibling to backend/) ---
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_root, "backend"))

# Load .env so DEMO_MODE / PRIVATE_KEY are available for the skip gate
from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

import pytest

# ---------------------------------------------------------------------------
# Skip gate — only run when explicitly configured for live 0G
# ---------------------------------------------------------------------------

_demo = os.getenv("DEMO_MODE", "true").strip().lower() in ("true", "1", "yes")
_has_key = bool(os.getenv("PRIVATE_KEY", "").strip())

pytestmark = [
    pytest.mark.skipif(_demo, reason="Live 0G test requires DEMO_MODE=false"),
    pytest.mark.skipif(not _has_key, reason="PRIVATE_KEY not set"),
]

# --- Imports after path setup (config.py loads .env) ---
from integrations.compute.compute_client import compute_client, ContentBlock


# ---------------------------------------------------------------------------
# 1. Simple inference — verify 0G provider responds + settlement succeeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simple_inference():
    """Send a trivial prompt through 0G and verify we get a real response."""
    # Reset health counters so we can assert cleanly
    compute_client._settlement_failures = 0
    compute_client._fallback_mode = False

    response = await compute_client.create_message(
        system="You are a helpful assistant. Reply in one short sentence.",
        messages=[{"role": "user", "content": "What is 2+2?"}],
        max_tokens=50,
    )

    # Response structure
    assert response.content, "Response should have content blocks"
    assert isinstance(response.content[0], ContentBlock)
    text = response.content[0].text
    assert text and len(text) > 0, "Response text should not be empty"
    assert "4" in text, f"Expected '4' in response, got: {text}"

    # Stop reason
    assert response.stop_reason in ("end_turn", "stop"), (
        f"Unexpected stop_reason: {response.stop_reason}"
    )

    # Settlement verification — processResponse must have succeeded
    assert compute_client._settlement_failures == 0, (
        "processResponse should have succeeded (0 failures)"
    )
    assert not compute_client._fallback_mode, (
        "Should NOT be in Anthropic fallback mode — inference should go through 0G"
    )


# ---------------------------------------------------------------------------
# 2. Provider discovery — verify compute_client found a real provider
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_provider_discovered():
    """After inference, compute_client should have a discovered provider."""
    # Ensure at least one call has been made to trigger discovery
    if compute_client._provider_address is None:
        await compute_client.create_message(
            system="Reply with OK.",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=10,
        )

    assert compute_client._provider_address is not None, "Provider address should be set"
    assert compute_client._provider_address.startswith("0x"), (
        f"Provider address should be an Ethereum address, got: {compute_client._provider_address}"
    )
    assert compute_client._provider_endpoint is not None, "Provider endpoint should be set"
    assert compute_client._provider_model is not None, "Provider model should be set"


# ---------------------------------------------------------------------------
# 3. Status endpoint — verify get_status() returns real data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_shows_real_provider():
    """get_status() should reflect the live 0G provider state."""
    # Trigger discovery if needed
    if compute_client._provider_address is None:
        await compute_client.create_message(
            system="Reply with OK.",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=10,
        )

    status = await compute_client.get_status()
    print(f"\nCompute status: {status}")

    assert status["demo_mode"] is False
    assert status["fallback_mode"] is False
    assert status["provider_address"] is not None
    assert status["provider_address"].startswith("0x")
    assert status["model"] is not None


# ---------------------------------------------------------------------------
# 4. Multi-turn conversation — verify context is maintained
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multi_turn_conversation():
    """Send a two-turn conversation and verify the model uses context."""
    compute_client._settlement_failures = 0

    response = await compute_client.create_message(
        system="You are a helpful assistant. Be concise.",
        messages=[
            {"role": "user", "content": "My name is Zara."},
            {"role": "assistant", "content": "Hello Zara! How can I help you?"},
            {"role": "user", "content": "What is my name?"},
        ],
        max_tokens=50,
    )

    text = response.content[0].text.lower()
    assert "zara" in text, f"Model should recall the name 'Zara', got: {text}"
    assert compute_client._settlement_failures == 0


# ---------------------------------------------------------------------------
# 5. E2E orchestrator turn — quest runtime through 0G
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_turn_via_0g():
    """Generate a minimal quest and run one orchestrator turn through 0G.

    This validates the full chain: OrchestratorAgent → compute_client → 0G provider.
    """
    from agents.quest_generation.models import (
        ActivityRef,
        Character,
        NarrativeUniverse,
        QuestOutput,
        Step,
    )
    from agents.quest_runtime.models import (
        CharacterTrust,
        QuestSession,
        SessionState,
    )
    from agents.quest_runtime.orchestrator import OrchestratorAgent

    compute_client._settlement_failures = 0
    compute_client._fallback_mode = False

    quest = QuestOutput(
        title="Test Quest",
        player_name="TestPlayer",
        narrative_universe=NarrativeUniverse(
            hook="A mysterious message arrives.",
            stakes="Everything.",
        ),
        characters=[
            Character(
                name="Shadow",
                personality="Mysterious and cryptic.",
                speech_pattern="Short. Cryptic.",
                secret="None.",
                relationship_to_player="Watcher",
                system_prompt=(
                    "You are Shadow, a mysterious figure who speaks in short, "
                    "cryptic sentences. You are watching the player."
                ),
            )
        ],
        steps=[
            Step(
                step_id=0,
                title="Begin",
                activity=ActivityRef(name="Start the quest"),
            )
        ],
    )

    session = QuestSession(
        quest_id=quest.quest_id,
        player_alias="TestPlayer",
        state=SessionState(
            current_step=0,
            characters_trust=[
                CharacterTrust(character_name="Shadow", trust_level=50)
            ],
        ),
    )

    orchestrator = OrchestratorAgent(quest=quest, session=session)
    events = await orchestrator.react(trigger="start")

    assert len(events) > 0, "Orchestrator should produce at least one event"
    # At least one event should have content
    has_content = any(e.content for e in events)
    assert has_content, "At least one event should have non-empty content"

    print(f"\nOrchestrator produced {len(events)} events:")
    for e in events:
        print(f"  [{e.type}] {e.character or '(system)'}: {e.content[:80]}...")

    assert compute_client._settlement_failures == 0, (
        "Settlement should succeed for orchestrator inference"
    )
    assert not compute_client._fallback_mode, (
        "Orchestrator should use 0G, not Anthropic fallback"
    )

# blockchain/ — Hedera Integration for OpenDND

Hedera-native blockchain layer: quest stake/lock system, HBAR rewards, NFT badges (HTS), immutable event logging (HCS), and x402 payment gating. No Solidity.

## Quick Start

### 1. Install dependencies

```bash
cd blockchain
uv sync --no-install-project
```

### 2. Configure `.env`

Create a testnet account at https://portal.hedera.com, then add to `blockchain/.env`:

```
HEDERA_OPERATOR_ID=0.0.XXXXX
HEDERA_OPERATOR_KEY=302e020100...
HEDERA_NETWORK=testnet
```

### 3. One-time testnet setup

Creates the NFT token class + HCS topic:

```bash
uv run --no-project python setup_testnet.py
```

Copy the output into your `.env`:

```
HEDERA_NFT_TOKEN_ID=0.0.XXXXX
HEDERA_QUEST_TOPIC_ID=0.0.XXXXX
```

## Integration in `main.py`

### Add the blockchain router (2 lines)

```python
from blockchain import blockchain_router

app.include_router(blockchain_router)
```

This exposes all endpoints under `/blockchain/`.

### Optional: x402 payment gating

Protect any endpoint behind an HBAR payment (HTTP 402 flow):

```python
from blockchain import X402PaymentMiddleware

app.add_middleware(
    X402PaymentMiddleware,
    protected_routes={
        "POST /generate": 100_000_000,  # 1 HBAR in tinybars
    },
)
```

Clients without payment get a `402 Payment Required` response with instructions. They pay on Hedera, then retry with the `X-PAYMENT-TX` header.

## Game Concept: Stake & Play

Players stake HBAR before starting a quest. If they complete it, they get their stake back plus a bonus from the redistribution pool. If they fail, the stake is burned.

```
Player stakes X HBAR  ──►  HBAR locked (escrow on operator account)
                                │
                    ┌───────────┴───────────┐
                    │                       │
              Quest SUCCESS            Quest FAIL
                    │                       │
          Refund stake + bonus        Stake burned
          + NFT badge minted          (feeds redistribution pool)
          + HCS log "stake.won"       + HCS log "stake.lost"
```

One player (the quest creator) stakes for the whole group. The bonus comes from redistributing lost stakes.

## API Endpoints

### Health

#### `GET /blockchain/health`

Check Hedera client connection.

```json
{"status": "ok", "network": "testnet"}
```

### Stake / Lock

#### `POST /blockchain/stake`

Lock HBAR before a quest. The player must have already sent the HBAR to the operator account (provide the tx hash as proof).

```json
{
  "quest_id": "quest-abc",
  "player_account_id": "0.0.12345",
  "amount": 100000000,
  "stake_tx_hash": "0.0.12345@1775292116.404456853"
}
```

`amount` is in tinybars (100,000,000 = 1 HBAR).

Returns a `StakeTx`:

```json
{
  "id": "abc123",
  "quest_id": "quest-abc",
  "player_account_id": "0.0.12345",
  "amount": 100000000,
  "status": "locked",
  "stake_tx_hash": "0.0.12345@1775292116.404456853",
  "refund_tx_hash": null,
  "bonus": 0,
  "nft_serial": null
}
```

Logs `stake.locked` on HCS.

#### `POST /blockchain/resolve`

Resolve a quest as win or lose.

**Win** — refunds the stake + bonus from redistribution pool + mints NFT badge:

```json
{
  "quest_id": "quest-abc",
  "outcome": "win",
  "nft_metadata": {"quest": "Cannes Mystery", "city": "Cannes"}
}
```

Returns `StakeTx` with `status: "won"`, `refund_tx_hash`, `bonus`, `nft_serial`.

**Lose** — stake stays burned, feeds the redistribution pool:

```json
{
  "quest_id": "quest-abc",
  "outcome": "lose"
}
```

Returns `StakeTx` with `status: "lost"`.

#### `GET /blockchain/stake/{quest_id}`

Check the stake status for a quest.

```json
{
  "quest_id": "quest-abc",
  "status": "locked",
  "amount": 100000000,
  "bonus": 0
}
```

### Rewards (direct)

#### `POST /blockchain/reward`

Issue a quest completion reward directly (HBAR transfer + optional NFT badge + HCS log). Use this for rewards outside the stake system.

```json
{
  "quest_id": "quest-abc",
  "player_account_id": "0.0.12345",
  "token_amount": 1,
  "nft_metadata": {"quest": "Cannes Mystery", "city": "Cannes"}
}
```

Returns a `RewardTx` with `tx_hash`, `nft_serial`, `status`.

### Events

#### `POST /blockchain/events`

Log a quest event to HCS (immutable on-chain log).

```json
{
  "quest_id": "quest-abc",
  "event_type": "checkpoint.verified",
  "payload": {"checkpoint": 2, "location": "Palais des Festivals"}
}
```

Returns `{"sequence_number": "3", "topic_event": "checkpoint.verified"}`.

### NFT

#### `POST /blockchain/nft/mint`

Mint a standalone NFT quest badge.

```json
{
  "metadata": {"quest": "Cannes Mystery", "city": "Cannes", "date": "2026-04-04"}
}
```

Returns `{"serial_number": 1}`.

### Transaction Verification

#### `GET /blockchain/tx/{tx_id}`

Verify a Hedera transaction via mirror node.

```
GET /blockchain/tx/0.0.12345@1775292116.404456853
```

Returns `{"tx_id": "...", "verified": true}`.

## Python API (direct import)

For internal use without HTTP:

```python
from blockchain import (
    initialize_hedera,
    reward_player,
    log_quest_event,
    stake_hbar,
    resolve_quest,
)

# At startup
await initialize_hedera()

# Stake flow
stake = await stake_hbar(
    quest_id="quest-abc",
    player_account_id="0.0.12345",
    amount=100_000_000,
    stake_tx_hash="0.0.12345@...",
)

# Quest won
result = await resolve_quest(
    quest_id="quest-abc",
    outcome="win",
    nft_metadata={"quest": "Cannes Mystery"},
)
# result.refund_tx_hash, result.bonus, result.nft_serial

# Quest lost
result = await resolve_quest(quest_id="quest-xyz", outcome="lose")
# result.status == "lost", HBAR burned

# Direct reward (outside stake system)
tx = await reward_player(
    quest_id="quest-abc",
    player_account_id="0.0.12345",
    token_amount=1,
    nft_metadata={"quest": "Cannes Mystery"},
)

# Log any event
seq = await log_quest_event(
    quest_id="quest-abc",
    event_type="quest.completed",
    payload={"player": "0.0.12345"},
)
```

## Architecture

```
blockchain/
  __init__.py          # Public API: reward_player(), stake_hbar(), resolve_quest(), etc.
  router.py            # FastAPI router — all HTTP endpoints
  config.py            # Hedera testnet client singleton
  models.py            # Pydantic models: RewardTx, StakeTx, HCSMessage
  hts_service.py       # HTS: HBAR transfers + NFT badge minting
  hcs_service.py       # HCS: immutable quest event logging
  stake_service.py     # Stake/lock logic: stake, resolve (win/lose), pool redistribution
  x402_middleware.py   # HTTP 402 payment gating middleware
  setup_testnet.py     # One-time: create NFT token + HCS topic
```

## HCS Events (on-chain log)

All key actions are logged immutably on the Hedera Consensus Service:

| Event | When |
|-------|------|
| `stake.locked` | Player stakes HBAR for a quest |
| `stake.won` | Quest succeeded — refund + bonus sent |
| `stake.lost` | Quest failed — stake burned |
| `reward.confirmed` | Direct reward sent (outside stake system) |
| `checkpoint.verified` | Player reaches a quest checkpoint |
| `quest.started` | Quest begins |
| `quest.completed` | Quest ends |

## Prize Tracks

- **AI & Agentic Payments on Hedera** ($6k) — AI agent pays autonomously via x402
- **No Solidity Allowed** ($3k) — everything uses native Hedera services (HTS, HCS)

## Verify on Testnet

- Transactions: https://hashscan.io/testnet
- NFT token: https://hashscan.io/testnet/token/{HEDERA_NFT_TOKEN_ID}
- HCS topic: https://hashscan.io/testnet/topic/{HEDERA_QUEST_TOPIC_ID}

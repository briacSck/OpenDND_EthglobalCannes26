# blockchain/ — Hedera Integration for OpenDND

Hedera-native blockchain layer: quest rewards (HBAR), NFT badges (HTS), immutable event logging (HCS), and x402 payment gating. No Solidity.

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

## API Endpoints

### `GET /blockchain/health`

Check Hedera client connection.

```json
{"status": "ok", "network": "testnet"}
```

### `POST /blockchain/reward`

Issue quest completion reward: HBAR transfer + optional NFT badge + HCS log.

```json
{
  "quest_id": "quest-abc",
  "player_account_id": "0.0.12345",
  "token_amount": 1,
  "nft_metadata": {"quest": "Cannes Mystery", "city": "Cannes"}
}
```

Returns a `RewardTx` with `tx_hash`, `nft_serial`, `status`.

### `POST /blockchain/events`

Log a quest event to HCS (immutable on-chain log).

```json
{
  "quest_id": "quest-abc",
  "event_type": "checkpoint.verified",
  "payload": {"checkpoint": 2, "location": "Palais des Festivals"}
}
```

Returns `{"sequence_number": "3", "topic_event": "checkpoint.verified"}`.

### `POST /blockchain/nft/mint`

Mint a standalone NFT quest badge.

```json
{
  "metadata": {"quest": "Cannes Mystery", "city": "Cannes", "date": "2026-04-04"}
}
```

Returns `{"serial_number": 1}`.

### `GET /blockchain/tx/{tx_id}`

Verify a Hedera transaction via mirror node.

```
GET /blockchain/tx/0.0.12345@1775292116.404456853
```

Returns `{"tx_id": "...", "verified": true}`.

## Python API (direct import)

For internal use without HTTP:

```python
from blockchain import reward_player, log_quest_event, initialize_hedera

# At startup
await initialize_hedera()

# Reward a player
tx = await reward_player(
    quest_id="quest-abc",
    player_account_id="0.0.12345",
    token_amount=1,
    nft_metadata={"quest": "Cannes Mystery"},
)

# Log an event
seq = await log_quest_event(
    quest_id="quest-abc",
    event_type="quest.completed",
    payload={"player": "0.0.12345"},
)
```

## Architecture

```
blockchain/
  __init__.py          # Public API: reward_player(), log_quest_event(), initialize_hedera()
  router.py            # FastAPI router with all HTTP endpoints
  config.py            # Hedera testnet client singleton
  models.py            # Pydantic models: RewardTx, HCSMessage
  hts_service.py       # HTS: HBAR transfers + NFT badge minting
  hcs_service.py       # HCS: immutable quest event logging
  x402_middleware.py   # HTTP 402 payment gating middleware
  setup_testnet.py     # One-time: create NFT token + HCS topic
```

## Prize Tracks

- **AI & Agentic Payments on Hedera** ($6k) — AI agent pays autonomously via x402
- **No Solidity Allowed** ($3k) — everything uses native Hedera services (HTS, HCS)

## Verify on Testnet

- Transactions: https://hashscan.io/testnet
- NFT token: https://hashscan.io/testnet/token/{HEDERA_NFT_TOKEN_ID}
- HCS topic: https://hashscan.io/testnet/topic/{HEDERA_QUEST_TOPIC_ID}

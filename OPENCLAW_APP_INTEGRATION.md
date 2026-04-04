# OpenClaw App Integration Guide

Integration reference for the app backend (Swift + Meta Glasses). OpenClaw exposes pure async Python functions — no HTTP transport, auth, or media upload logic. The app backend owns all of that.

---

## Ownership Boundary

| Concern | OpenClaw | App Backend |
|---------|----------|-------------|
| Quest generation | X | |
| Runtime orchestration | X | |
| Character AI agents | X | |
| Proof verification (voice/image) | X | |
| Booking automation | X | |
| Memory persistence (0G Storage) | X | |
| Reward anchoring (Hedera) | X | |
| Auth (Dynamic wallet JWT) | | X |
| Transport (SSE / WebSocket) | | X |
| Media upload (glasses audio/video) | | X |
| CORS | | X |
| Client-specific formatting | | X |

---

## Callable Service Functions

All functions live in `agents/integration/service.py`. Import via:

```python
from agents.integration import (
    start_quest_session,
    handle_player_message,
    handle_player_action,
    submit_voice_proof,
    submit_image_or_video_proof,
    confirm_booking,
    generate_quest_recap,
)
```

### start_quest_session

```python
async def start_quest_session(
    quest: QuestOutput,
    player_name: str = "",
    allow_arg: bool = False,
) -> tuple[QuestSession, OrchestratorAgent, list[RuntimeEventEnvelope]]
```

Creates a session, loads player memory, builds the orchestrator, fires the opening sequence. The caller must store the returned `session` and `orchestrator` in its own registry.

**Parameters:**
- `quest` — a generated `QuestOutput` (from `/generate`)
- `player_name` — player display name or wallet address
- `allow_arg` — player consents to ARG events (fake emails, SMS)

**Returns:** `(session, orchestrator, events)` — the opening events include the first character message.

### handle_player_message

```python
async def handle_player_message(
    inp: PlayerMessageInput,
    quest: QuestOutput,
    session: QuestSession,
    orchestrator: OrchestratorAgent,
) -> tuple[str, list[RuntimeEventEnvelope]]
```

Player sends a direct message to a character. The character responds, then the orchestrator may trigger follow-ups (other characters chiming in, narrative beats, artifacts).

**Returns:** `(character_response_text, all_events)` — the first event is always the character's reply.

### handle_player_action

```python
async def handle_player_action(
    inp: PlayerActionInput,
    quest: QuestOutput,
    session: QuestSession,
    orchestrator: OrchestratorAgent,
) -> list[RuntimeEventEnvelope]
```

Generic player action (move, voice, custom). The orchestrator decides how characters react.

### submit_voice_proof

```python
async def submit_voice_proof(
    inp: VoiceProofInput,
    quest: QuestOutput,
    session: QuestSession,
) -> ProofResult
```

Transcribes audio via Whisper and matches against the current step's verification target. If verified, appends a `checkpoint.verified` event to the session.

### submit_image_or_video_proof

```python
async def submit_image_or_video_proof(
    inp: ImageProofInput | VideoProofInput,
    quest: QuestOutput,
    session: QuestSession,
) -> ProofResult
```

For `VideoProofInput`: extracts first frame via ffmpeg, then runs image verification. Uses Anthropic vision (Claude Haiku) to check if the image matches the step's `success_condition`. If verified, stores the description in `session.best_proof_description` for recap.

### confirm_booking

```python
async def confirm_booking(
    inp: BookingConfirmationInput,
    session: QuestSession,
    orchestrator: OrchestratorAgent,
) -> list[RuntimeEventEnvelope]
```

Player confirms a pending booking. Appends a `booking.completed` event and triggers a character to narrate the confirmation in-character.

### generate_quest_recap

```python
async def generate_quest_recap(
    quest: QuestOutput,
    session: QuestSession,
) -> QuestRecapResponse
```

Generates a post-quest summary using the LLM. Call after quest completion and reward.

---

## Input Models

Defined in `agents/integration/models.py`.

### PlayerMessageInput

| Field | Type | Description |
|-------|------|-------------|
| session_id | str | Active session ID |
| character_name | str | Name of the character to talk to |
| content | str | The player's message text |

### PlayerActionInput

| Field | Type | Description |
|-------|------|-------------|
| session_id | str | Active session ID |
| action_type | str | `message \| voice \| move \| ignore \| custom` |
| content | str | Action text content |
| target_character | str | Character involved, if any |
| gps_coords | list[float] \| None | `[lat, lon]` from device |

### VoiceProofInput

| Field | Type | Description |
|-------|------|-------------|
| session_id | str | Active session ID |
| audio_b64 | str | Base64-encoded audio data |
| encoding | str | `pcm_16khz \| aac \| opus` (default: pcm_16khz) |
| duration_ms | int | Audio duration in milliseconds |

### ImageProofInput

| Field | Type | Description |
|-------|------|-------------|
| session_id | str | Active session ID |
| frame_b64 | str | Base64-encoded JPEG or PNG |
| media_type | str | `image/jpeg \| image/png` (default: image/jpeg) |

### VideoProofInput

| Field | Type | Description |
|-------|------|-------------|
| session_id | str | Active session ID |
| video_b64 | str | Base64-encoded MP4 video |

### BookingConfirmationInput

| Field | Type | Description |
|-------|------|-------------|
| session_id | str | Active session ID |
| booking_ref | str | Booking reference from the provider |

---

## Output Models

### RuntimeEventEnvelope

Every event from the runtime is wrapped in this stable envelope. Use `type` for routing (e.g. SSE `event:` field) and `payload` for full data.

| Field | Type | Description |
|-------|------|-------------|
| event_id | str | Unique event UUID |
| type | str | Event type (see table below) |
| ts | str | ISO 8601 timestamp |
| character_name | str \| None | Character involved, if any |
| content | str | Primary text content |
| voice_line | str \| None | TTS script from `voice_script` field, or None |
| payload | dict | Full `OrchestratorEvent.model_dump()` |

### QuestRecapResponse

| Field | Type | Description |
|-------|------|-------------|
| quest_id | str | Quest identifier |
| session_id | str | Session identifier |
| narrative_summary | str | 3-5 sentence story recap |
| highlights | list[str] | 3-5 memorable moments |
| next_quest_teaser | str | Hook for the next quest |
| grade | str | A-F grade |
| reward_tx_hash | str \| None | Hedera transaction hash |
| memory_root_hash | str \| None | 0G Storage root hash |

### ProofResult

| Field | Type | Description |
|-------|------|-------------|
| verified | bool | Whether the proof passed |
| confidence | float | 0.0-1.0 score |
| transcript | str \| None | Voice: Whisper transcript |
| matched_keyword | str \| None | Voice: keyword that matched |
| description | str \| None | Image: what the vision model saw |
| step_id | int \| None | Step this proof was submitted for |

---

## Runtime Event Types

| Type | When | Key fields |
|------|------|------------|
| `character_message` | A character speaks to the player | `character_name`, `content`, `voice_line` |
| `artifact` | Generated content sent to the player | `payload.artifact` (type, description, generation_prompt) |
| `timer` | Countdown started | `payload.timer_seconds`, `character_name` |
| `group_chat` | Multi-character conversation (player included) | `content` (formatted messages) |
| `forwarded_message` | Intercepted conversation (player observes) | `content` |
| `arg_event` | Out-of-game event (email, SMS, social) | `payload.arg_channel`, `character_name` |
| `checkpoint.verified` | Proof accepted for current step | `content` (verification summary) |
| `booking.prepared` | Booking intent created | `content` (JSON of BookingIntent) |
| `booking.completed` | Booking confirmed | `content` (JSON with booking_ref) |
| `booking.pending_human` | Booking needs manual action | `content` (JSON of BookingResult) |
| `quest.reward.confirmed` | On-chain reward submitted | `content` (tx hash info) |

---

## Proof Flow

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ Meta Glasses │────>│ App Backend  │────>│   OpenClaw   │
│ audio/video  │     │ decode b64   │     │ verify_voice │
└─────────────┘     └──────────────┘     │ verify_image │
                                          └──────┬───────┘
                                                 │
                                          ProofResult
                                          + checkpoint.verified event
```

**Voice proof:** Audio (PCM 16kHz from glasses) → base64 → `submit_voice_proof()` → Whisper transcription → case-insensitive keyword match against `Verification.target` / `Verification.success_condition`.

**Image proof:** JPEG frame from glasses → base64 → `submit_image_or_video_proof(ImageProofInput)` → Anthropic Claude Haiku vision → YES/NO against `Verification.success_condition`.

**Video proof:** MP4 clip → base64 → `submit_image_or_video_proof(VideoProofInput)` → ffmpeg extracts first frame → same image verification path. Requires ffmpeg on the server.

---

## Booking Confirmation Flow

```
1. App backend calls existing POST /quests/{id}/booking
   → OpenClaw runs prepare_booking + complete_booking
   → Returns BookingIntent + BookingResult

2. If result.status == "pending_human":
   → App shows instructions + confirmation_url to player
   → Player completes booking manually

3. Player confirms in app:
   → App backend calls confirm_booking(BookingConfirmationInput)
   → OpenClaw appends booking.completed event
   → Orchestrator triggers character narration
   → Returns narration events
```

---

## Recap Flow

Call after quest completion + reward:

```
1. Quest completes (current_step >= len(steps))
   → Memory persisted to 0G, player profile updated

2. POST /quests/{id}/reward → RewardTx with tx_hash

3. App backend calls generate_quest_recap(quest, session)
   → LLM summarizes the adventure
   → Returns QuestRecapResponse with summary, highlights, grade
```

---

## DEMO_MODE Behavior

Set `DEMO_MODE=true` in `.env` to bypass all external services.

| Component | DEMO_MODE=true behavior |
|-----------|------------------------|
| Voice proof | Returns `verified=true` + mock transcript |
| Image proof | Returns `verified=true` + mock description |
| Recap | Returns static mock data |
| Booking | Mock `completed` status instantly |
| Memory | In-memory dict store, SHA-256 mock hashes |
| Reward | Fake tx_hash, status=DEMO |
| LLM (compute_client) | Falls back to Anthropic directly |

---

## End-to-End Example

```python
from agents.integration import *

# 1. Generate a quest (via existing /generate endpoint)
quest = ...  # QuestOutput from POST /generate

# 2. Start session
session, orchestrator, events = await start_quest_session(
    quest=quest,
    player_name="0x1234...abcd",
)
# events → [RuntimeEventEnvelope(type="character_message", ...)]
# Store session + orchestrator in your registry keyed by session.session_id

# 3. Player talks to a character
response_text, events = await handle_player_message(
    inp=PlayerMessageInput(
        session_id=session.session_id,
        character_name="Zara",
        content="Where should I go next?",
    ),
    quest=quest,
    session=session,
    orchestrator=orchestrator,
)
# response_text → "Head to the old café on Rue d'Antibes..."
# events → [character_message, maybe artifact or timer]

# 4. Voice proof from glasses
proof = await submit_voice_proof(
    inp=VoiceProofInput(
        session_id=session.session_id,
        audio_b64="<base64 PCM data>",
        encoding="pcm_16khz",
        duration_ms=3000,
    ),
    quest=quest,
    session=session,
)
# proof.verified → True/False

# 5. Image proof from glasses
proof = await submit_image_or_video_proof(
    inp=ImageProofInput(
        session_id=session.session_id,
        frame_b64="<base64 JPEG>",
        media_type="image/jpeg",
    ),
    quest=quest,
    session=session,
)

# 6. Confirm booking
events = await confirm_booking(
    inp=BookingConfirmationInput(
        session_id=session.session_id,
        booking_ref="BOOK-ABC123",
    ),
    session=session,
    orchestrator=orchestrator,
)
# events → [booking.completed, character narration]

# 7. Trigger reward (via existing POST /quests/{id}/reward)
# reward_tx = ...

# 8. Generate recap
recap = await generate_quest_recap(quest=quest, session=session)
# recap.narrative_summary → "L'agent a traversé 5 étapes..."
# recap.highlights → ["Premier contact...", "La révélation...", ...]
# recap.grade → "B"
```

---

## Booking Integration

### Field Flow: quest_generation → booking_agent

| `ActivityRef` field (quest_generation) | `prepare_booking()` param | Notes |
|----------------------------------------|---------------------------|-------|
| `name` | `activity_name` | Required — adapter returns `None` if empty |
| `address` | `location` | Falls back to quest location if empty |
| `booking_url` | `url` | Required — adapter returns `None` if empty |
| `price_eur` | `budget_eur` | Used as budget ceiling for the booking |
| `booking_required` | _(filter only)_ | Used to select which activities need booking |

### Automatic vs Manual Booking

Activities are selected for booking preparation when `booking_required == True` **OR** `booking_url != ""` (fallback for quests generated before the Curator prompt update).

After `prepare_booking()` inspects the booking page:

| `BookingIntent.requires_human_action` | Meaning | App behavior |
|---------------------------------------|---------|--------------|
| `False` | No login, CAPTCHA, or payment wall | `complete_booking()` can finish automatically |
| `True` | Login, CAPTCHA, or payment form detected | App shows `confirmation_url` + `instructions` to player |

### Usage

```python
from agents.integration import prepare_quest_bookings

# After quest generation, before session start
quest = ...  # QuestOutput from /generate
bookings = await prepare_quest_bookings(quest)

for intent in bookings:
    if intent.requires_human_action:
        # → emit booking.pending_human event to app
        # → app shows intent.booking_url + intent.reason to player
    else:
        result = await complete_booking(intent)
        # → emit booking.completed event
```

### Events Emitted

| Event | When |
|-------|------|
| `booking.prepared` | After `prepare_quest_bookings()` returns intents |
| `booking.pending_human` | Intent requires manual player action |
| `booking.completed` | Booking confirmed (auto or via `confirm_booking()`) |

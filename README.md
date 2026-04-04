# OpenD&D — AI-Powered Real-Life Quest System

Backend engine that generates and runs immersive, narrative-driven quests in the real world. Players explore a city while AI characters contact them through a mobile app — text, voice, documents, timers. No actors, no planted objects. The real world is the backdrop; the story lives in the app.

Built for **ETH Global Cannes 2026**. Designed to plug into a mobile frontend + **OpenClaw** for on-chain purchases (museum tickets, activity bookings, rewards).

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Mobile App (frontend)                     │
│         React Native / Flutter — connects via REST + WS          │
└──────────┬──────────────┬───────────────┬───────────────────────┘
           │ REST          │ REST           │ WebSocket
           ▼              ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐
│  /generate   │  │  /play/*     │  │  /play/voice/{session}/  │
│  Quest Gen   │  │  Runtime API │  │  {character}             │
│  Pipeline    │  │              │  │  Voice Pipeline          │
└──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘
       │                 │                      │
       ▼                 ▼                      ▼
┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐
│ Storyteller  │  │ Orchestrator │  │  STT (Deepgram)        │
│ + Curator    │  │  (invisible) │  │  → Claude (streaming)  │
│ + Judge      │  │              │  │  → TTS (ElevenLabs)    │
│ + Characters │  │ Character    │  │                        │
│   Initializer│  │ Agents (AI)  │  │  Bidirectional audio   │
└──────────────┘  └──────────────┘  └────────────────────────┘
       │                 │
       ▼                 ▼
┌──────────────────────────────────┐
│         Claude API (Anthropic)    │
│  Storyteller, Orchestrator,       │
│  Character agents — all Claude    │
└──────────────────────────────────┘
```

---

## API Endpoints (FastAPI)

**Entry point:** `main.py` → `uvicorn main:app --port 8000`

### Quest Generation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/research` | Run city research agent (scrapes activities, POIs, restaurants) |
| `POST` | `/generate` | Full pipeline: research → generate quest → store in memory |

### Quest Runtime (live play)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/play/start` | Start a session. Returns `session_id` + opening events |
| `POST` | `/play/action` | Player sends a generic action (move, custom). Returns orchestrator events |
| `POST` | `/play/message` | Player texts a specific character. Returns character reply + follow-up events |
| `POST` | `/play/heartbeat` | Client pings every ~30s. Triggers idle nudges if player inactive >5min |
| `GET`  | `/play/status/{session_id}` | Current session state (step, trust levels, event count) |
| `WS`   | `/play/voice/{session_id}/{character_name}` | Real-time voice conversation with a character |

### Utility

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/health` | Health check |

---

## Data Models

All models are Pydantic. Two main domains: **generation** and **runtime**.

### Generation Models (`agents/quest_generation/models.py`)

#### `QuestRequest` — what the player asks for
```json
{
  "goal": "investigation and cultural discovery",
  "vibe": "espionage, thriller",
  "duration": "1h",
  "budget": 250,
  "location": "Cannes",
  "difficulty": "life-maxing",
  "players": 1,
  "datetime": "2026-04-05 14:00",
  "tone": "high_stakes",
  "skill": "investigation"
}
```

`difficulty`: `easy-peasy` | `life-maxing` | `god-mode`
`tone`: `loufoque` (absurd/funny) | `high_stakes` (thriller/espionage)

#### `QuestOutput` — the full generated quest (main object)
```
QuestOutput
├── quest_id: str (UUID)
├── title: str
├── tone: str
├── player_name: str
├── generation_meta: GenerationMeta
│   ├── storyteller_curator_iterations: int
│   ├── judge_iterations: int
│   └── judge_final_score: int
├── narrative_universe: NarrativeUniverse
│   ├── hook: str              // first message — irresistible
│   ├── context: str           // world/situation
│   ├── protagonist: str       // player's role
│   └── stakes: str            // what's at risk
├── pre_quest_bundle: PreQuestBundle
│   ├── email: EmailBundle
│   ├── voicemail: VoicemailBundle
│   ├── pdf: PdfBundle
│   └── playlist: PlaylistBundle
├── character_system: CharacterSystem
│   ├── max_active: int
│   └── principals: list[str]
├── characters: list[Character]      // 5+ characters
├── budget_confirmed: BudgetConfirmed
├── steps: list[Step]                // 6 physical locations/activities
├── narrative_beats: list[NarrativeBeat]  // flexible story moments
├── narrative_tensions: list[str]    // forces/dilemmas at play
├── twist: dict                      // central twist + revelation variants
├── resolution_principles: list[str] // rules for building ending at runtime
├── trust_dynamics: dict             // per-character behavior by trust level
└── resolution: Resolution
    ├── skill_gained: str
    └── prize: Prize (xp_total, token_amount, nft_metadata)
```

#### `Character`
```json
{
  "name": "Lena Voss",
  "age": 34,
  "type": "principal",
  "archetype": "love_interest",
  "personality": "...",
  "speech_pattern": "...",
  "relationship_to_player": "...",
  "secret": "...",
  "evolution_rules": "...",
  "reactions_imprevues": "...",
  "voice_id": "elevenlabs_abc123",
  "memory_state": { "trust_level": 50, "dormant": false },
  "system_prompt": "..."
}
```

`type`: `principal` | `secondary` | `invoked`
`archetype`: `mastermind` | `electron_libre` | `genie_arrogant` | `fantome` | `love_interest`

#### `Step` — a physical location/activity in the quest
```json
{
  "step_id": 1,
  "is_collaborative": false,
  "is_skill_step": true,
  "title": "The Carlton Facade",
  "activity": {
    "name": "Hotel Carlton",
    "address": "58 Bd de la Croisette",
    "price_eur": 0,
    "duration_minutes": 15,
    "booking_url": "",
    "category": "culture"
  },
  "narrative_intro": "...",
  "instruction": "...",
  "player_action": "Photograph the facade and describe the cupolas",
  "gps_trigger": {
    "type": "message",
    "character": "Lena Voss",
    "content_brief": "..."
  },
  "camera_prompt": "...",
  "tension": { "type": "revelation", "description": "...", "resolution": "..." },
  "character_interactions": [
    {
      "character": "Lena Voss",
      "trigger": "GPS proximity",
      "phone_version": "...",
      "rayban_version": { "script": "...", "audio_type": "narration" },
      "awaits_response": true
    }
  ],
  "verification": {
    "method": "camera_ai",
    "target": "...",
    "success_condition": "...",
    "success_reaction": "...",
    "failure_fallback": "...",
    "timeout_reaction": "..."
  },
  "walking_minutes_from_previous": 3,
  "blockchain_event": "step_1_complete",
  "skill_xp": 15
}
```

`verification.method`: `zk_location` | `camera_ai` | `text_answer`
`gps_trigger.type`: `message` | `document` | `audio` | `image`
`tension.type`: `complication` | `revelation` | `choix_sous_pression` | `bifurcation` | `risque_calcule` | `none`

### Runtime Models (`agents/quest_runtime/models.py`)

#### `QuestSession` — a live play session
```json
{
  "session_id": "uuid",
  "quest_id": "uuid",
  "player_alias": "Agent",
  "state": {
    "current_step": 2,
    "beats_completed": [0, 1],
    "characters_trust": [
      { "character_name": "Lena Voss", "trust_level": 65, "interaction_count": 4 }
    ],
    "narrative_arc": "suspicion",
    "time_since_last_event_seconds": 120,
    "total_elapsed_seconds": 1800,
    "player_speed": "normal"
  },
  "events_log": [],
  "actions_log": [],
  "conversations": {
    "Lena Voss": [{ "role": "player", "content": "..." }]
  },
  "active": true
}
```

#### `PlayerAction` — what the player does
```json
{
  "type": "message",
  "content": "I found the inscription",
  "gps_coords": [43.5528, 7.0174],
  "target_character": "Lena Voss"
}
```

`type`: `message` | `voice` | `move` | `ignore` | `custom`

#### `OrchestratorEvent` — what gets sent to the player
```json
{
  "event_id": "uuid",
  "type": "character_message",
  "character": "Lena Voss",
  "content": "The actual message text",
  "voice_script": "...",
  "artifact": null,
  "timer_seconds": 0,
  "arg_channel": ""
}
```

`type`: `character_message` | `artifact` | `timer` | `group_chat` | `forwarded_message` | `arg_event`
`artifact.type`: `classified_document` | `intercepted_audio` | `handwritten_note` | `map` | `coded_message`

#### Request Objects for the Mobile App

| Object | Endpoint | Key fields |
|--------|----------|------------|
| `PlayStartRequest` | `/play/start` | `quest_id`, `player_name`, `allow_arg`, `player_email`, `player_phone` |
| `PlayActionRequest` | `/play/action` | `session_id`, `action: PlayerAction` |
| `PlayMessageRequest` | `/play/message` | `session_id`, `character_name`, `content` |
| `PlayHeartbeatRequest` | `/play/heartbeat` | `session_id`, `gps_coords?`, `weather?` |

### City Research Models (`agents/city_research/models.py`)

`CityContext` holds everything the generation pipeline knows about a city:

```
CityContext
├── location: LocationInfo (city, neighborhood, lat/lon, weather)
├── city_description: str
├── activities: list[Activity]     // name, price, address, category, duration, booking_url
├── restaurants: list[Restaurant]
├── shops: list[Shop]
├── events: list[Event]
├── points_of_interest: list[POI]
├── transport: TransportInfo
├── current_news: list[NewsItem]   // for high_stakes narrative anchoring
└── raw_notes: str
```

---

## Agent Architecture

### 1. Quest Generation Pipeline (`agents/quest_generation/pipeline.py`)

Four phases, all checkpointed to `checkpoints/`:

```
Phase 1: Storyteller <-> Curator dialogue
         Storyteller asks Curator for real activities,
         Curator responds with what exists + prices.
         Output: concept (title, characters, narrative universe, twist)

Phase 2: Judge evaluation
         Scores the quest 0-100 across 7 criteria.
         If < 75/100: clears checkpoints, regenerates from scratch with feedback.
         Max 3 iterations.

Phase 3: Character enrichment
         CharacterInitializer generates full system prompts
         + ElevenLabs voice generation per character.

Phase 4: Assembly
         Merges everything into a QuestOutput.
```

**Storyteller** (`agents/quest_generation/storyteller.py`):
- Uses Claude with tool_use (ask_curator, submit_concept, submit_step, submit_meta)
- Phased generation: concept -> steps (one by one) -> meta
- Temperature 1.0 for maximum creativity
- Supports judge feedback injection for regeneration

**Curator** (`agents/quest_generation/curator.py`):
- Has the city's real activity catalog
- Enforces budget, walkability (5min max between steps), no escape games
- Returns real prices, addresses, booking URLs

**Judge** (`agents/quest_generation/judge.py`):
- 7-criteria evaluation: hook (15), plot (15), activities (15), characters (15), flexibility (15), tone (15), budget (10)
- Threshold: 75/100
- Returns actionable feedback per criterion

### 2. Quest Runtime (`agents/quest_runtime/`)

**Orchestrator** (`orchestrator.py`):
- Invisible to the player — everything goes through characters
- Decides which character speaks, when, why
- Tools: `send_character_message`, `send_artifact`, `start_timer`, `create_group_chat`, `trigger_arg_event`, `update_state`
- Reacts to: player actions, heartbeats, idle detection (>5min), timer expiry
- Manages trust levels, narrative beats, dramatic pacing (~1 event/5min)
- Rising tension arc: calm -> suspicious -> danger -> climax -> twist -> resolution

**Character Agents** (`character_agent.py`):
- One AI agent per character, each with its own system prompt + conversation history
- Autonomous: responds in-character, adapts tone to trust level
- Two modes: `respond()` (player texts them) and `initiate()` (orchestrator asks them to contact player)
- Streaming support via `respond_stream()` for voice pipeline
- Trust-based behavior:
  - < 30: suspicious, distant, testing
  - 30-60: neutral, professional
  - 60-80: complicit, inside jokes, sensitive info
  - > 80: intimate, vulnerable, reveals secrets

### 3. Voice Pipeline (`agents/voice/`)

Real-time bidirectional voice over WebSocket:

```
Player mic -> PCM 16kHz -> [WebSocket] -> Deepgram STT -> transcript
    -> Claude streaming (character agent) -> text chunks
    -> ElevenLabs TTS (character's unique voice) -> MP3 chunks -> [WebSocket] -> speaker
```

**WebSocket Protocol** (`/play/voice/{session_id}/{character_name}`):

Client -> Server:
- Binary frames: raw PCM audio (16kHz, 16-bit, mono, little-endian)
- `{"type": "end_audio"}` — end of speech
- `{"type": "interrupt"}` — cut character's response

Server -> Client:
- `{"type": "transcript", "text": "...", "is_final": bool}` — STT result
- `{"type": "text_chunk", "text": "..."}` — character response text (for subtitles)
- `{"type": "voice_chunk", "audio": "<base64 mp3>", "format": "mp3"}` — audio
- `{"type": "end_turn"}` — character finished speaking
- `{"type": "followup_event", "event": {...}}` — orchestrator follow-up events
- `{"type": "error", "message": "..."}` — error

### 4. Artifact Renderer (`agents/artifact_renderer.py`)

Generates real files sent to the player's "vault":

| Artifact type | Output | Description |
|--------------|--------|-------------|
| `briefing` | PDF | Quest briefing (hook, situation, role) — dark themed |
| `email` | PDF | Styled email with CONFIDENTIAL watermark |
| `classified_document` | PDF | Redacted document with stamps and margin notes |
| `voicemail` | MP3 | Character's voice via ElevenLabs TTS |
| `coded_message` | PDF | Aged paper effect with coffee stain |
| `intercepted_audio` | MP3 | Multi-character conversation (each in their own voice) |
| `playlist` | HTML | Spotify search links, styled card |

---

## OpenClaw Integration Points

The backend is ready for on-chain purchases via OpenClaw at these touchpoints:

### 1. Activity Bookings (per step)
Each `Step.activity` has:
- `price_eur` — the cost
- `booking_url` — where to book
- `blockchain_event` — event name to emit on-chain (e.g. `"step_1_complete"`)

**Flow:** Mobile app calls OpenClaw to purchase the ticket -> confirms to backend -> step unlocks.

### 2. Pre-Quest Bundle Purchase
`PreQuestBundle` contains items (email PDF, voicemail MP3, classified doc, playlist) that can be gated behind a single OpenClaw transaction at quest start.

### 3. Step Completion Rewards
Each step has `skill_xp` and optional `blockchain_event`. On step completion:
- Backend emits the event in the `/play/action` response
- Mobile app triggers OpenClaw to mint XP tokens or record completion on-chain

### 4. Final Resolution / NFT
`Resolution.prize` contains:
```json
{
  "xp_total": 500,
  "token_amount": 100,
  "nft_metadata": {
    "city": "Cannes",
    "date": "2026-04-05",
    "quest_title": "Salt and Ashes",
    "characters_met": ["Lena Voss", "Dante Salieri"],
    "ending_chosen": "betrayal_arc"
  }
}
```
Mobile app calls OpenClaw to mint a quest completion NFT with this metadata.

### 5. Verification Methods
`Step.verification.method` includes `zk_location` — designed for zero-knowledge proof of location via OpenClaw. The mobile app can use on-chain ZK proofs to verify the player was physically at the step location.

### 6. Budget Flow
```
Player budget (e.g. 250 EUR)
├── Pre-quest bundle: ~15 EUR (paid via OpenClaw at quest start)
├── Activities: variable (paid per step via OpenClaw as player progresses)
└── Reward pool: ~30% of budget (distributed as tokens at resolution)
```

### Suggested OpenClaw Integration

```
POST /openclaw/purchase    — buy a ticket/booking for a step activity
POST /openclaw/mint-xp     — mint XP tokens on step completion
POST /openclaw/mint-nft    — mint quest completion NFT
GET  /openclaw/balance     — player's token/XP balance
POST /openclaw/verify      — verify on-chain ZK location proof
```

---

## Mobile App Integration Guide

### 1. Quest Flow

```
App startup
  |-> POST /generate { QuestRequest }
  |   -> Returns QuestOutput (cache locally)
  |
Player taps "Start Quest"
  |-> POST /play/start { quest_id, player_name, allow_arg }
  |   -> Returns session_id + opening events (first character contact)
  |
Game loop (while session.active):
  |-> POST /play/heartbeat { session_id, gps_coords }     // every 30s
  |    -> May return idle nudge events
  |
  |-> POST /play/message { session_id, character_name, content }
  |    -> Returns character reply + orchestrator follow-ups
  |
  |-> POST /play/action { session_id, action: PlayerAction }
  |    -> For GPS moves, photos, custom actions
  |
  |-> WS /play/voice/{session_id}/{character_name}
       -> Real-time voice call with a character
```

### 2. What the Mobile App Needs to Render

| Event type | UI element |
|------------|-----------|
| `character_message` | Chat bubble from character (use `character` field for avatar/color) |
| `artifact` | File viewer — PDF, audio player, image. Use `artifact.type` to pick renderer |
| `timer` | Countdown overlay with `timer_seconds` |
| `group_chat` | Group chat UI with multiple character avatars |
| `forwarded_message` | "Intercepted" message with visual treatment (dimmed, redacted style) |
| `arg_event` | Out-of-app notification (email, SMS, social) — only if player opted in via `allow_arg` |

### 3. GPS Integration

- Send `gps_coords` in every heartbeat request
- Each step has an `activity.address` — geocode it for navigation
- `gps_trigger` content auto-unlocks when player is within ~50m of a step location
- Use `walking_minutes_from_previous` to show estimated walking time between steps
- Steps are designed to be max 5 min walk apart

### 4. Camera / AI Vision

- Player photographs real-world elements (facades, signs, statues, street art)
- Send as `PlayerAction` with `type: "custom"` and `content: "[photo] description of what they see"`
- Backend's AI interprets the photo in the narrative context and characters react
- Steps with `camera_prompt` indicate what the player should photograph and how AI interprets it
- `verification.method: "camera_ai"` means the step is verified by photo analysis

### 5. Character List & Trust

- `QuestOutput.characters` gives the full character list at quest start
- Each character has: `name`, `archetype`, `voice_id`, `relationship_to_player`
- Trust levels update in every `/play/action` and `/play/message` response under `state.characters_trust`
- Use trust levels to adjust UI (e.g. lock icon for low trust characters, glow for high trust)

### 6. Pre-Quest Bundle (vault)

Before the quest starts, render the `pre_quest_bundle`:
- **Email**: show as an in-app email notification
- **Voicemail**: audio player with character name
- **PDF**: classified document viewer
- **Playlist**: link to Spotify or in-app player

These build anticipation. Can be gated behind OpenClaw payment.

---

## Running Locally

### Prerequisites

```bash
pip install -r requirements.txt
```

### Environment Variables (`.env`)

```
ANTHROPIC_AUTH_TOKEN=sk-ant-...      # Claude API key
ANTHROPIC_BASE_URL=                   # optional proxy URL
ANTHROPIC_MODEL=claude-opus-4-6       # or claude-sonnet-4-6
ELEVENLABS_API_KEY=...                # for voice generation + TTS
DEEPGRAM_API_KEY=...                  # for STT (speech-to-text)
```

### Generate a Quest

```bash
python run_generate.py
# -> Outputs quest_highstakes.json
# -> Checkpoints saved in checkpoints/
```

### Run the API Server

```bash
python main.py
# -> FastAPI on http://localhost:8000
# -> Swagger docs at http://localhost:8000/docs
```

### Test in Terminal (no mobile app needed)

```bash
# Full simulation with voice, artifacts, colors
python run_simulate.py
# Commands: @CharName: message | /voice Name | /goto step N | /photo desc | /next | /status

# Simpler text-only CLI
python run_play.py
# Commands: msg <char> <text> | move <place> | see <desc> | wait | status | chars | steps
```

### Generate Character Voices

```bash
python generate_voices.py
# -> Creates ElevenLabs voices for all characters in checkpoints/
```

---

## File Structure

```
.
├── main.py                          # FastAPI app — all REST + WS endpoints
├── run_generate.py                  # Standalone quest generation (hardcoded Cannes context)
├── run_simulate.py                  # Full terminal simulation (voice, artifacts, colors)
├── run_play.py                      # Simple terminal CLI (text only, debug orchestrator)
├── generate_voices.py               # Batch ElevenLabs voice generation
├── requirements.txt
├── quest_highstakes.json            # Generated quest output (example)
├── checkpoints/                     # Pipeline checkpoints (concept, steps, characters, meta)
├── artifacts/                       # Generated files (PDFs, MP3s, HTML)
│
├── agents/
│   ├── quest_generation/
│   │   ├── models.py                # All Pydantic models (QuestOutput, Character, Step, ...)
│   │   ├── pipeline.py              # Orchestrates: Storyteller <-> Curator -> Judge -> Characters
│   │   ├── storyteller.py           # Claude agent — creates narrative via tool_use (phased)
│   │   ├── curator.py               # Activity catalog manager, budget enforcer
│   │   ├── judge.py                 # Quality evaluator (7 criteria, 75/100 threshold)
│   │   ├── characters.py            # Character enrichment (system prompts + voice gen)
│   │   └── prompts.py               # All system prompts (storyteller, curator, judge)
│   │
│   ├── quest_runtime/
│   │   ├── models.py                # QuestSession, PlayerAction, OrchestratorEvent, ...
│   │   ├── orchestrator.py          # Invisible runtime — drives the quest live via tool_use
│   │   └── character_agent.py       # Autonomous AI agent per character (text + streaming)
│   │
│   ├── voice/
│   │   ├── stt.py                   # Deepgram WebSocket streaming STT
│   │   ├── tts.py                   # ElevenLabs streaming TTS + voice design API
│   │   ├── router.py                # FastAPI WebSocket endpoint for voice calls
│   │   └── test_client.py
│   │
│   ├── city_research/
│   │   ├── models.py                # CityContext, Activity, Restaurant, POI, NewsItem, ...
│   │   ├── agent.py                 # Research agent (gathers real city data)
│   │   └── tools.py                 # Search tools (Google, TripAdvisor, Luma, etc.)
│   │
│   └── artifact_renderer.py         # Generates PDFs (reportlab), MP3s (ElevenLabs), HTML
```

---

## Key Design Decisions

- **Characters have no body.** They are AI agents that communicate only through the app. No physical meetings, no planted objects, no bluffing about seeing the player. The real world is a backdrop.
- **Emergent narrative.** No predefined endings (A/B/C). The story emerges from trust dynamics, player choices, and resolution principles. The orchestrator composes the ending at runtime.
- **Non-blocking verifications.** The player always progresses. Success gives bonuses (XP, trust, exclusive info); failure adapts the story but never blocks.
- **Scenario framework, not script.** The generation pipeline produces flexible narrative beats and arcs. The runtime orchestrator decides exact timing and form.
- **Locked activities, flexible narrative.** Once activities are booked (via OpenClaw), the physical locations don't change. But the narrative justification around them adapts in real-time.
- **All state is in-memory.** Sessions, quests, and orchestrators live in Python dicts. Replace with a database for production.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI + Uvicorn |
| LLM (all agents) | Anthropic Claude (Opus / Sonnet) |
| Data models | Pydantic v2 |
| Speech-to-text | Deepgram Nova-2 (WebSocket streaming) |
| Text-to-speech | ElevenLabs Multilingual v2 (streaming + voice design) |
| PDF generation | ReportLab |
| Audio playback | pydub + sounddevice |
| HTTP client | httpx |

---

Built for [ETH Global Cannes 2026](https://ethglobal.com/)

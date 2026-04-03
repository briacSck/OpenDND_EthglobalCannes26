# OpenD&D

**AI-powered real-life quest system** built for ETH Global Cannes 2026.

OpenD&D generates immersive, character-driven quests set in real cities using real locations, real news, and real activities. Players interact with autonomous AI characters via text and voice while an invisible orchestrator drives the narrative in real-time.

## Architecture

```
[Quest Generation Pipeline]              [Live Runtime]

POST /research                            POST /play/start
  City Research Agent                       Orchestrator (invisible supervisor)
  -> real places, events, news              -> creates CharacterAgent per character
                                            -> manages pacing (~5 min events)
POST /generate                              -> triggers beats, artifacts, ARG
  Storyteller <-> Curator dialogue
  -> Judge evaluation loop                POST /play/message
  -> Character enrichment                   Player talks directly to a character
  -> QuestOutput (scenario framework)       -> CharacterAgent responds in-character
                                            -> Orchestrator may trigger chime-ins

                                          POST /play/action
                                            Generic player actions (move, voice, etc.)

                                          POST /play/heartbeat
                                            Keep-alive, idle detection, chime-ins
```

### Multi-Agent System

| Agent | Role |
|-------|------|
| **City Research Agent** | Gathers real locations, activities, restaurants, events, and news for a given city using web search tools |
| **Storyteller** | Creates the narrative universe, characters, and scenario framework in dialogue with the Curator |
| **Curator** | Matches narrative needs to real available activities, enforces budget |
| **Judge** | Scores quest quality (100-point rubric), sends feedback for revision |
| **Character Initializer** | Enriches each character with a full system prompt, voice, speech patterns, and reaction rules |
| **Orchestrator** | Invisible runtime supervisor: decides which character speaks when, triggers narrative beats, artifacts, timers, and ARG events |
| **Character Agents** | One autonomous AI agent per character. Players chat directly with them. Characters can also initiate contact on their own |

### Quest Tones

- **loufoque** -- Absurd, funny, Wes Anderson x Monty Python x The Office
- **high_stakes** -- Tense, credible, anchored in real news. Da Vinci Code x Killing Eve x Mission Impossible. Features character archetypes (Mastermind, Love Interest, Fantome, etc.) and romantic tension

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/research` | Run city research for a location |
| `POST` | `/generate` | Full pipeline: research + generate quest |
| `POST` | `/play/start` | Start a live quest session |
| `POST` | `/play/message` | Send a message to a specific character |
| `POST` | `/play/action` | Send a generic player action |
| `POST` | `/play/heartbeat` | Keep-alive ping, triggers idle events |
| `GET` | `/play/status/{session_id}` | Get session status |
| `GET` | `/health` | Health check |

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Set ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL

# Run
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Example Flow

```bash
# 1. Generate a quest
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "culture et mystere",
    "duration": "3h",
    "budget": 150,
    "location": "Paris",
    "datetime": "2026-04-05 14:00",
    "tone": "high_stakes",
    "skill": "investigation"
  }'

# 2. Start a session (use quest_id from response)
curl -X POST http://localhost:8000/play/start \
  -H "Content-Type: application/json" \
  -d '{"quest_id": "YOUR_QUEST_ID"}'

# 3. Talk to a character
curl -X POST http://localhost:8000/play/message \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "YOUR_SESSION_ID",
    "character_name": "Moriarty",
    "content": "Qui es-tu et pourquoi tu me contactes ?"
  }'
```

## Key Design Decisions

- **Scenario framework, not rigid script** -- The generation pipeline produces a flexible narrative framework (beats, arcs, trust dynamics). The runtime orchestrator decides the exact timing and form
- **Locked activities** -- Once booked, real-world activities never change. Only the narrative justifications around them adapt in real-time
- **Character-driven** -- No visible game master. Everything flows through character personas. The orchestrator is invisible
- **Autonomous character agents** -- Each character is its own AI agent with a rich system prompt, conversation history, and personality. The orchestrator sends directives, characters write their own messages
- **Chime-in** -- Characters can spontaneously contact the player without being asked, driven by the orchestrator's pacing logic

## Tech Stack

- **FastAPI** -- API framework
- **Anthropic Claude** -- LLM backbone (all agents)
- **Pydantic** -- Data models and validation
- **DuckDuckGo** -- News search for real-world anchoring (high_stakes)

## License

MIT

---

Built for [ETH Global Cannes 2026](https://ethglobal.com/)

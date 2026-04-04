"""Storyteller Agent — creates the narrative, dialogues with Curator.

Phased generation: instead of one massive submit_quest tool call,
the Storyteller submits in 3 smaller pieces so the API proxy doesn't choke.
  Phase 1: Curator dialogue (ask_curator)
  Phase 2: submit_concept (title, player_name, narrative_universe, pre_quest_bundle, characters, narrative_tensions, twist)
  Phase 3: submit_step x N (one step at a time for speed)
  Phase 4: submit_meta (narrative_beats, resolution_principles, trust_dynamics, resolution)
"""

from __future__ import annotations

import asyncio
import json
import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

from agents.city_research.models import CityContext
from agents.quest_generation.models import QuestRequest
from agents.quest_generation.curator import CuratorAgent
from agents.quest_generation.prompts import build_storyteller_prompt

load_dotenv()

CHECKPOINT_DIR = "checkpoints"


def log(msg: str):
    print(msg, flush=True)


def _save_checkpoint(name: str, data):
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    path = os.path.join(CHECKPOINT_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"  [Checkpoint] Saved {name}")


def _load_checkpoint(name: str):
    path = os.path.join(CHECKPOINT_DIR, f"{name}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        log(f"  [Checkpoint] Loaded {name} from cache")
        return data
    return None


MAX_DIALOGUE_TURNS = 2

# --- Tool definitions ---

ASK_CURATOR_TOOL = {
    "name": "ask_curator",
    "description": "Ask the Curator for real activities. Describe what you need narratively — the Curator will respond with what actually exists, prices, and remaining budget.",
    "input_schema": {
        "type": "object",
        "properties": {
            "request": {
                "type": "string",
                "description": "Your request to the Curator: what types of locations/activities you need, area constraints, atmosphere, price, etc.",
            }
        },
        "required": ["request"],
    },
}

SUBMIT_CONCEPT_TOOL = {
    "name": "submit_concept",
    "description": "Phase 1/3 — Submit the concept: title, player_name, narrative universe, pre-quest bundle, characters, narrative tensions, and twist.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "player_name": {"type": "string", "description": "Player's first name — characters call them by their real first name, no codename/alias"},
            "narrative_universe": {
                "type": "object",
                "properties": {
                    "hook": {"type": "string", "description": "The first message — irresistible, presupposes an existing role"},
                    "context": {"type": "string"},
                    "protagonist": {"type": "string"},
                    "stakes": {"type": "string"},
                },
                "required": ["hook", "context", "protagonist", "stakes"],
            },
            "pre_quest_bundle": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "object",
                        "properties": {
                            "from_character": {"type": "string"},
                            "subject": {"type": "string"},
                            "body": {"type": "string"},
                        },
                    },
                    "voicemail": {
                        "type": "object",
                        "properties": {
                            "from_character": {"type": "string"},
                            "script": {"type": "string"},
                            "duration_seconds": {"type": "integer"},
                        },
                    },
                    "pdf": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "content_brief": {"type": "string"},
                        },
                    },
                    "playlist": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "mood": {"type": "string"},
                            "genre_keywords": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
            "characters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                        "type": {"type": "string", "description": "principal | secondary"},
                        "archetype": {"type": "string"},
                        "personality": {"type": "string"},
                        "speech_pattern": {"type": "string", "description": "3+ examples of typical lines"},
                        "relationship_to_player": {"type": "string"},
                        "secret": {"type": "string"},
                        "unlock_conditions": {"type": "array", "items": {"type": "string"}},
                        "evolution_rules": {"type": "string", "description": "How this character changes based on player behavior (not just scores, real changes in behavior/allegiance/tone)"},
                        "reactions_imprevues": {"type": "string", "description": "How this character handles the unexpected, their red lines, reaction under pressure"},
                    },
                    "required": ["name", "personality", "secret", "evolution_rules", "reactions_imprevues"],
                },
            },
            "narrative_tensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Forces/dilemmas at play — NOT predefined endings A/B/C",
            },
            "twist": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "The central twist of the story"},
                    "revelation_variants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Different ways the player can discover the twist depending on their path",
                    },
                },
                "required": ["description", "revelation_variants"],
            },
        },
        "required": ["title", "player_name", "narrative_universe", "characters", "narrative_tensions", "twist"],
    },
}

SUBMIT_STEP_TOOL = {
    "name": "submit_step",
    "description": "Submit ONE quest step with all its details.",
    "input_schema": {
        "type": "object",
        "properties": {
            "step_id": {"type": "integer"},
            "is_collaborative": {"type": "boolean"},
            "is_skill_step": {"type": "boolean"},
            "title": {"type": "string"},
            "activity": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "address": {"type": "string"},
                    "price_eur": {"type": "number"},
                    "duration_minutes": {"type": "integer"},
                    "booking_url": {"type": "string"},
                    "category": {"type": "string"},
                },
            },
            "narrative_intro": {"type": "string"},
            "instruction": {"type": "string"},
            "tension": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "description": {"type": "string"},
                    "resolution": {"type": "string"},
                },
            },
            "character_interactions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "character": {"type": "string"},
                        "trigger": {"type": "string", "description": "Condition via the app (GPS proximity, photo sent, time elapsed) — NEVER a physical meeting"},
                        "phone_version": {"type": "string"},
                        "rayban_version": {
                            "type": "object",
                            "properties": {
                                "script": {"type": "string"},
                                "duration_seconds": {"type": "integer"},
                                "audio_type": {"type": "string"},
                                "camera_mode": {
                                    "type": "object",
                                    "properties": {
                                        "enabled": {"type": "boolean"},
                                        "purpose": {"type": "string"},
                                    },
                                },
                                "contextual_music": {
                                    "type": "object",
                                    "properties": {
                                        "enabled": {"type": "boolean"},
                                        "track_type": {"type": "string"},
                                        "duration_seconds": {"type": "integer"},
                                    },
                                },
                            },
                        },
                        "awaits_response": {"type": "boolean"},
                    },
                },
            },
            "verification": {
                "type": "object",
                "properties": {
                    "method": {"type": "string"},
                    "target": {"type": "string"},
                    "success_condition": {"type": "string"},
                    "success_reaction": {"type": "string", "description": "Narrative reaction if the player succeeds (bonus, exclusive info, trust++)"},
                    "failure_fallback": {"type": "string", "description": "What happens if the player fails — the story ALWAYS continues"},
                    "timeout_reaction": {"type": "string", "description": "Character message if the player takes too long"},
                },
            },
            "walking_minutes_from_previous": {
                "type": "integer",
                "description": "Walking time in minutes from the previous step (max 5 min)",
            },
            "player_action": {
                "type": "string",
                "description": "The CONCRETE action the player must perform: photograph X, find Y, observe Z, describe W. Must be active, not passive.",
            },
            "gps_trigger": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "message | document | audio | image"},
                    "character": {"type": "string", "description": "Character who sends/triggers the content"},
                    "content_brief": {"type": "string", "description": "What gets unlocked when the player arrives"},
                },
                "description": "Content automatically unlocked when player reaches this location (GPS proximity)",
            },
            "camera_prompt": {
                "type": "string",
                "description": "What the player should photograph at this location and how AI will interpret it narratively. Empty if no photo action at this step.",
            },
            "blockchain_event": {"type": "string"},
            "unlock_message": {"type": "string"},
            "skill_xp": {"type": "integer"},
        },
        "required": ["step_id", "title", "activity", "narrative_intro", "instruction", "player_action", "gps_trigger"],
    },
}

SUBMIT_META_TOOL = {
    "name": "submit_meta",
    "description": "Phase 3/3 — Submit narrative beats, resolution principles, trust dynamics and resolution.",
    "input_schema": {
        "type": "object",
        "properties": {
            "narrative_beats": {
                "type": "array",
                "description": "Flexible key moments the runtime orchestrator will place dynamically",
                "items": {
                    "type": "object",
                    "properties": {
                        "beat_id": {"type": "integer"},
                        "description": {"type": "string"},
                        "characters_involved": {"type": "array", "items": {"type": "string"}},
                        "earliest_step": {"type": "integer"},
                        "latest_step": {"type": "integer"},
                        "tension_level": {"type": "string", "description": "low | medium | high | climax"},
                        "can_be_skipped": {"type": "boolean"},
                        "possible_triggers": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["beat_id", "description", "characters_involved", "tension_level"],
                },
            },
            "resolution_principles": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Rules for building the ending at runtime — NOT predefined endings. E.g., 'if trust Vera > 70 and trust Castaldi < 30 → Vera reveals the twist while protecting the player'",
            },
            "trust_dynamics": {
                "type": "object",
                "description": "For each character: BEHAVIORS that change based on trust (not just scores). E.g., {name: {low: 'actively lies, gives false leads', medium: 'cooperates but hides their secret', high: 'confides, reveals their real agenda'}}",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "low": {"type": "string", "description": "Character behavior when trust is low"},
                        "medium": {"type": "string", "description": "Character behavior when trust is medium"},
                        "high": {"type": "string", "description": "Character behavior when trust is high"},
                    },
                },
            },
            "resolution": {
                "type": "object",
                "properties": {
                    "skill_gained": {"type": "string"},
                    "prize": {
                        "type": "object",
                        "properties": {
                            "xp_total": {"type": "integer"},
                            "token_amount": {"type": "integer"},
                        },
                    },
                },
            },
        },
        "required": ["narrative_beats", "resolution_principles", "trust_dynamics"],
    },
}

# Phase 1 tools (curator dialogue + concept submission)
PHASE1_TOOLS = [ASK_CURATOR_TOOL, SUBMIT_CONCEPT_TOOL]
# Phase 2 tool (steps)
PHASE2_TOOLS = [SUBMIT_STEP_TOOL]
# Phase 3 tool (meta)
PHASE3_TOOLS = [SUBMIT_META_TOOL]

# Legacy monolithic tool — kept for revise() which is simpler
SUBMIT_QUEST_TOOL = {
    "name": "submit_quest",
    "description": "Submit the complete corrected final quest.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "player_name": {"type": "string"},
            "narrative_universe": {"type": "object"},
            "pre_quest_bundle": {"type": "object"},
            "characters": {"type": "array", "items": {"type": "object"}},
            "steps": {"type": "array", "items": {"type": "object"}},
            "narrative_beats": {"type": "array", "items": {"type": "object"}},
            "narrative_tensions": {"type": "array", "items": {"type": "string"}},
            "twist": {"type": "object"},
            "trust_dynamics": {"type": "object"},
            "resolution_principles": {"type": "array", "items": {"type": "string"}},
            "resolution": {"type": "object"},
        },
        "required": ["title", "player_name", "narrative_universe", "characters", "steps", "narrative_beats", "narrative_tensions", "twist", "trust_dynamics", "resolution_principles"],
    },
}


class StorytellerAgent:
    def __init__(self, request: QuestRequest, city_context: CityContext):
        self.client = AsyncAnthropic(
            base_url=os.getenv("ANTHROPIC_BASE_URL"),
            api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
        )
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
        self.request = request
        self.city_context = city_context
        self.curator = CuratorAgent(city_context, request.budget)

        self.system_prompt = build_storyteller_prompt(
            tone=request.tone,
            skill=request.skill,
            budget=request.budget,
        )
        self.temperature = 1.0  # Max allowed by proxy (0-1 range)
        self.curator_iterations = 0
        self.judge_feedback = ""  # Injected by pipeline if regenerating after Judge rejection

    async def generate(self) -> dict:
        """Run the phased Storyteller pipeline and return the merged quest dict."""

        # --- Phase 1: Curator dialogue + concept ---
        concept = _load_checkpoint("concept")
        if concept is None:
            log("\n  [Storyteller] Phase 1/3: Curator dialogue + concept...")
            concept = await self._phase_curator_and_concept()
            _save_checkpoint("concept", concept)
        else:
            log("\n  [Storyteller] Phase 1/3: Skipped — loaded from checkpoint")
        log(f"  [Storyteller] Concept received: \"{concept.get('title', '???')}\" — {len(concept.get('characters', []))} characters")

        # --- Phase 2: Steps ---
        steps_data = _load_checkpoint("steps_all")
        if steps_data is None:
            log("\n  [Storyteller] Phase 2/3: Generating steps...")
            steps_data = await self._phase_steps(concept)
            _save_checkpoint("steps_all", steps_data)
        else:
            log("\n  [Storyteller] Phase 2/3: Skipped — loaded from checkpoint")
        log(f"  [Storyteller] Steps received: {len(steps_data.get('steps', []))} steps")

        # --- Phase 3: Meta (beats, resolution_principles, trust, resolution) ---
        meta_data = _load_checkpoint("meta")
        if meta_data is None:
            log("\n  [Storyteller] Phase 3/3: Generating meta (beats, decisions, trust)...")
            meta_data = await self._phase_meta(concept, steps_data)
            _save_checkpoint("meta", meta_data)
        else:
            log("\n  [Storyteller] Phase 3/3: Skipped — loaded from checkpoint")
        log(f"  [Storyteller] Meta received: {len(meta_data.get('narrative_beats', []))} beats")

        # --- Merge all phases ---
        merged = {**concept, **steps_data, **meta_data}
        return merged

    async def _phase_curator_and_concept(self) -> dict:
        """Phase 1: Curator dialogue then submit_concept."""
        user_prompt = self._build_initial_prompt()
        messages = [{"role": "user", "content": user_prompt}]

        for i in range(MAX_DIALOGUE_TURNS + 3):
            log(f"\n--- Storyteller iteration {i + 1} (Phase 1) ---")

            # After enough curator turns, force submit_concept
            force_concept = self.curator_iterations >= MAX_DIALOGUE_TURNS
            tools = PHASE1_TOOLS
            extra_kwargs = {}
            if force_concept:
                tools = [SUBMIT_CONCEPT_TOOL]
                extra_kwargs["tool_choice"] = {"type": "tool", "name": "submit_concept"}

            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=16000,
                    temperature=self.temperature,
                    system=self.system_prompt,
                    tools=tools,
                    messages=messages,
                    **extra_kwargs,
                )
            except Exception as e:
                log(f"  [Storyteller] API error: {e} — waiting 10s and retrying...")
                await asyncio.sleep(10)
                if len(messages) > 3:
                    messages = [messages[0]] + messages[-2:]
                messages.append({
                    "role": "user",
                    "content": "API error. Call submit_concept immediately with what you have.",
                })
                continue

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "text":
                        log(f"  [Storyteller] {block.text[:200]}...")
                    elif block.type == "tool_use":
                        if block.name == "submit_concept":
                            log("  [Storyteller] Concept submitted!")
                            return block.input

                        if block.name == "ask_curator":
                            self.curator_iterations += 1
                            log(f"  [Storyteller -> Curator] Tour {self.curator_iterations}: {block.input['request'][:150]}...")
                            curator_response = await self.curator.respond(block.input["request"])
                            log(f"  [Curator -> Storyteller] {curator_response[:200]}...")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": curator_response,
                            })

                messages.append({"role": "assistant", "content": response.content})
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "end_turn":
                for block in response.content:
                    if block.type == "text":
                        log(f"  [Storyteller] {block.text[:300]}")
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": "Excellent! Now call submit_concept with: title, player_name, narrative_universe, pre_quest_bundle, characters (minimum 5), narrative_tensions, and twist.",
                })

            elif response.stop_reason == "max_tokens":
                messages.append({"role": "assistant", "content": response.content})
                dangling = [b.id for b in response.content if b.type == "tool_use"]
                if dangling:
                    dummies = [{"type": "tool_result", "tool_use_id": tid, "content": "[truncated]"} for tid in dangling]
                    messages.append({"role": "user", "content": dummies + [
                        {"type": "text", "text": "Truncated. Call submit_concept immediately."}
                    ]})
                else:
                    messages.append({"role": "user", "content": "Truncated. Call submit_concept immediately."})

        raise RuntimeError("Storyteller Phase 1 did not submit concept after max iterations")

    async def _phase_steps(self, concept: dict) -> dict:
        """Phase 2: Generate steps ONE BY ONE for fast proxy responses."""
        char_names = [c["name"] for c in concept.get("characters", [])]
        num_steps = 6  # Target number of steps

        concept_summary = f"""**Title**: {concept.get('title', '')}
**Player name**: {concept.get('player_name', '')}
**Hook**: {concept.get('narrative_universe', {}).get('hook', '')}
**Context**: {concept.get('narrative_universe', {}).get('context', '')}
**Stakes**: {concept.get('narrative_universe', {}).get('stakes', '')}
**Characters**: {', '.join(char_names)}
**Narrative tensions**: {', '.join(concept.get('narrative_tensions', []))}"""

        all_steps = []

        # Load already-generated steps from checkpoints
        for i in range(1, num_steps + 1):
            cached = _load_checkpoint(f"step_{i}")
            if cached is not None:
                all_steps.append(cached)
            else:
                break

        for step_num in range(len(all_steps) + 1, num_steps + 1):
            log(f"\n--- Storyteller Step {step_num}/{num_steps} (Phase 2) ---")

            # Build context with previous steps
            prev_steps_text = ""
            if all_steps:
                prev_steps_text = "\n\n**Previously generated steps:**\n" + "\n".join(
                    f"- Step {s['step_id']}: {s['title']} — {s['activity'].get('name', '?')} ({s['activity'].get('price_eur', 0)}€)"
                    for s in all_steps
                )

            messages = [{"role": "user", "content": f"""Here is the quest concept:

{concept_summary}
{prev_steps_text}

Generate **step {step_num}** (out of {num_steps} total). Call submit_step with:
- step_id, title, activity (name, address, price_eur, duration_minutes, category)
- narrative_intro (immersive text), instruction (what the player must do)
- **player_action**: a CONCRETE action (photograph X, find Y, observe Z, describe W) — NEVER passive
- **gps_trigger**: content unlocked when player arrives (type: message|document|audio|image, character, content_brief)
- **camera_prompt**: what the player should photograph and how AI interprets it (if applicable)
- **walking_minutes_from_previous**: walking time from previous step (MAX 5 minutes)
- tension (type, description, resolution)
- character_interactions (2-3 character interactions, each with phone_version + rayban_version)
- verification (method, target, success_condition, success_reaction, failure_fallback, timeout_reaction)
- blockchain_event, unlock_message, skill_xp

IMPORTANT CONSTRAINTS:
- This step MUST be within 5 min walk of the previous step (walkable route, no taxi/bus)
- The player must have a CLEAR, ACTIVE thing to do (not just "go there and listen")
- Include a GPS trigger that unlocks content when the player arrives
{"- This step must be COLLABORATIVE (is_collaborative=true)." if step_num == 3 else ""}
{"- This step must be a SKILL STEP (is_skill_step=true)." if step_num in (2, 5) else ""}
{"- THIS IS THE FINAL STEP. It MUST take place INSIDE the Musée des Explorations du Monde (Place de la Castre, Le Suquet). The player enters the museum — tickets are provided by the app (OpenClaw). The action happens inside: the player explores the Mediterranean antiquities collection, finds specific artifacts, photographs them. The museum's medieval tower panorama can be a bonus. Activity price_eur=6, booking_url='https://www.cannesticket.com/offres/musee-des-explorations-du-monde-cannes-fr-5366287/'." if step_num == num_steps else ""}
Be detailed and immersive."""}]

            for attempt in range(5):
                try:
                    response = await self.client.messages.create(
                        model=self.model,
                        max_tokens=8000,
                        temperature=self.temperature,
                        system=self.system_prompt,
                        tools=PHASE2_TOOLS,
                        tool_choice={"type": "tool", "name": "submit_step"},
                        messages=messages,
                    )
                except Exception as e:
                    wait = 5 * (attempt + 1)  # 5s, 10s, 15s, 20s, 25s
                    log(f"  [Storyteller] API error on step {step_num}: {e} — retry {attempt + 1}, waiting {wait}s...")
                    await asyncio.sleep(wait)
                    continue

                for block in response.content:
                    if block.type == "tool_use" and block.name == "submit_step":
                        step_data = block.input
                        step_data["step_id"] = step_num
                        all_steps.append(step_data)
                        _save_checkpoint(f"step_{step_num}", step_data)
                        log(f"  [Storyteller] Step {step_num} submitted: \"{step_data.get('title', '?')}\" — {step_data.get('activity', {}).get('name', '?')}")
                        break
                else:
                    continue
                break

        log(f"  [Storyteller] All {len(all_steps)} steps generated!")
        return {"steps": all_steps}

    async def _phase_meta(self, concept: dict, steps_data: dict) -> dict:
        """Phase 3: Generate narrative_beats, resolution_principles, trust_dynamics, resolution."""
        char_names = [c["name"] for c in concept.get("characters", [])]
        step_titles = [f"Step {s.get('step_id', '?')}: {s.get('title', '?')}" for s in steps_data.get("steps", [])]

        messages = [{"role": "user", "content": f"""You have submitted the concept and steps. Here is the summary:

**Title**: {concept.get('title', '')}
**Characters**: {', '.join(char_names)}
**Steps**:
{chr(10).join(f'  - {t}' for t in step_titles)}

Now generate the final part:

1. **narrative_beats**: flexible key moments (beat_id, description, characters_involved, earliest_step, latest_step, tension_level, can_be_skipped, possible_triggers). At least 6-8 beats.

2. **resolution_principles**: rules for building the ending at RUNTIME (NOT predefined endings A/B/C). E.g., "if the player betrayed Vera AND gained Castaldi's trust → the twist is revealed by Castaldi". At least 5-8 principles covering major cases.

3. **trust_dynamics**: for EACH character ({', '.join(char_names)}), an object with BEHAVIORS per trust level (low/medium/high) — not numeric scores. E.g., {{low: "lies, gives false leads", medium: "cooperates but hides their secret", high: "confides, reveals their real agenda"}}.

4. **resolution**: skill_gained + prize (xp_total, token_amount).

Call submit_meta with all of this."""}]

        for i in range(4):
            log(f"\n--- Storyteller iteration {i + 1} (Phase 3: Meta) ---")

            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=100000,
                    temperature=self.temperature,
                    system=self.system_prompt,
                    tools=PHASE3_TOOLS,
                    tool_choice={"type": "tool", "name": "submit_meta"},
                    messages=messages,
                )
            except Exception as e:
                log(f"  [Storyteller] API error: {e} — waiting 10s and retrying...")
                await asyncio.sleep(10)
                messages.append({"role": "user", "content": "API error. Call submit_meta immediately."})
                continue

            if response.stop_reason == "tool_use":
                for block in response.content:
                    if block.type == "text":
                        log(f"  [Storyteller] {block.text[:200]}...")
                    elif block.type == "tool_use" and block.name == "submit_meta":
                        log(f"  [Storyteller] Meta submitted!")
                        return block.input

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": "Call submit_meta now."})

            elif response.stop_reason == "end_turn":
                for block in response.content:
                    if block.type == "text":
                        log(f"  [Storyteller] {block.text[:200]}...")
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": "Call submit_meta with narrative_beats, resolution_principles, trust_dynamics and resolution."})

            elif response.stop_reason == "max_tokens":
                messages.append({"role": "assistant", "content": response.content})
                dangling = [b.id for b in response.content if b.type == "tool_use"]
                if dangling:
                    dummies = [{"type": "tool_result", "tool_use_id": tid, "content": "[truncated]"} for tid in dangling]
                    messages.append({"role": "user", "content": dummies + [
                        {"type": "text", "text": "Truncated. Call submit_meta immediately."}
                    ]})
                else:
                    messages.append({"role": "user", "content": "Truncated. Call submit_meta immediately."})

        raise RuntimeError("Storyteller Phase 3 did not submit meta")

    async def revise(self, quest_raw: dict, feedback: list[dict]) -> dict:
        """Revise a quest based on Judge feedback. Uses monolithic submit for simplicity."""

        feedback_text = "\n".join(
            f"- [{fb['agent']}] {fb['issue']} -> {fb['instruction']}"
            for fb in feedback
        )

        messages = [
            {"role": "user", "content": f"""Here is the quest you produced:

```json
{json.dumps(quest_raw, ensure_ascii=False, indent=2)[:50000]}
```

The Judge returned this feedback:

{feedback_text}

Fix the quest based on this feedback. Call submit_quest with the corrected version."""}
        ]

        # No ask_curator in revise — just fix the JSON, don't redo research
        tools = [SUBMIT_QUEST_TOOL]

        for i in range(4):
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=100000,
                system=self.system_prompt,
                tools=tools,
                tool_choice={"type": "tool", "name": "submit_quest"},
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                for block in response.content:
                    if block.type == "tool_use" and block.name == "submit_quest":
                        return block.input

                # Shouldn't happen with tool_choice forced, but handle gracefully
                messages.append({"role": "assistant", "content": response.content})
                dangling = [b.id for b in response.content if b.type == "tool_use"]
                if dangling:
                    dummies = [{"type": "tool_result", "tool_use_id": tid, "content": "Call submit_quest now."} for tid in dangling]
                    messages.append({"role": "user", "content": dummies})
                else:
                    messages.append({"role": "user", "content": "Call submit_quest now."})
            else:
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": "Call submit_quest with the corrected version."})

        raise RuntimeError("Storyteller revision did not produce a result")

    def _judge_feedback_section(self) -> str:
        if not self.judge_feedback:
            return ""
        return f"""

## PREVIOUS ATTEMPT REJECTED BY JUDGE — FIX THESE ISSUES

Your previous quest was rejected. You MUST address ALL of these issues in this new attempt:

{self.judge_feedback}

DO NOT repeat the same mistakes. Pay special attention to duration, step diversity, and walkability."""

    def _build_initial_prompt(self) -> str:
        news_section = ""
        if self.request.tone == "high_stakes" and self.city_context.current_news:
            news_items = "\n".join(
                f"- **{n.name}** ({n.date}) — {n.summary} [Narrative relevance: {n.relevance_for_narrative}]"
                for n in self.city_context.current_news
            )
            news_section = f"""
## Current events & geopolitical context (REAL ANCHORING)
Use these verifiable real facts to anchor your narrative. The player should be able
to google these elements and find real articles.

{news_items}
"""

        return f"""Here is the context for the quest to create:

## Player request
- **Skill**: {self.request.skill or 'urban exploration'}
- **Vibe**: {self.request.vibe}
- **Duration**: {self.request.duration}
- **Budget**: {self.request.budget}€
- **Location**: {self.request.location}
- **Difficulty**: {self.request.difficulty}
- **Players**: {self.request.players}
- **Date/Time**: {self.request.datetime}
- **Tone**: {self.request.tone}

## City essence
{self.city_context.city_description}

## What you already know about the city
- Main neighborhood: {self.city_context.location.neighborhood}
- Weather: {self.city_context.location.weather}, {self.city_context.location.temperature}
- Transport: {self.city_context.transport.notes}
{news_section}
Generation happens in 3 phases:
1. First, dialogue with the Curator to find activities. Then call **submit_concept** with title, player_name, narrative_universe, pre_quest_bundle, characters (minimum 5), narrative_tensions, and twist.
2. Next you'll be asked for detailed steps.
3. Then narrative beats, resolution principles, and trust dynamics.

IMPORTANT REMINDERS:
- No physical interactions with characters or objects. Everything goes through the app (messages, calls, documents).
- submit_concept must contain narrative_tensions (NOT predefined endings A/B/C) and a twist with revelation_variants.
- Each character must have evolution_rules and reactions_imprevues.

Start by thinking about your narrative direction, then ask the Curator for the
activities you need. Go!{self._judge_feedback_section()}"""

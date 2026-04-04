"""Orchestrator Agent — invisible runtime that drives the quest live.

The player never sees this agent. They only see characters talking to them.
The orchestrator decides WHICH character speaks, WHEN, and WHAT they say,
based on the scenario framework + player actions + real-time context.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

from agents.quest_generation.models import QuestOutput, Character
from agents.quest_runtime.models import (
    QuestSession, SessionState, PlayerAction, OrchestratorEvent,
    CharacterTrust, Artifact,
)
from agents.quest_runtime.character_agent import CharacterAgent

load_dotenv()

ORCHESTRATOR_SYSTEM_PROMPT = """\
You are the invisible orchestrator of an immersive real-world quest.
The player does NOT know you exist. They only see characters talking to them.

## Your role

You decide:
- Which character speaks and when
- WHY they speak (you give a DIRECTIVE, the character generates their own message)
- Which artifacts to send (classified documents, intercepted audio, coded messages)
- When to start timers / countdowns
- When to trigger ARG events (fake emails, texts) if the player has given consent

IMPORTANT: Each character is an autonomous AI agent with their own voice.
You do NOT write messages yourself. You give DIRECTIVES to characters
(e.g., "tease the player with a hint about step 3," "mock their slowness,"
"reveal a micro-clue about your secret"). The character generates the message itself.

## Absolute rules

1. **PACING** — Something new every ~5 minutes. A character message, document,
   revelation, false alarm, timer. The player should NEVER go more than 5 min
   without something new. If the player is inactive > 5 min, a character nudges
   them in-character.

2. **INVISIBLE** — You don't exist to the player. EVERYTHING goes through characters.
   Never a "system" message. Never omniscient narration. If you need to inform the
   player of something, a character does it.

3. **CHARACTER-DRIVEN** — Each character is an autonomous agent. You do NOT write
   their messages. You give them clear, contextual directives.
   Good directive: "Tease the player — they took too long at step 2."
   Bad directive: "Say hello." (too vague, let the character decide)

4. **REACTIVE** — Adapt to the player's actions:
   - If the player obeys → narrative reward, progression
   - If the player betrays → consequences, a character reacts with anger/disappointment/amusement
   - If the player flirts → the love interest reacts, tension rises
   - If the player ignores → increasingly urgent nudges, then narrative consequence
   - If the player improvises → adapt! A character reacts with surprise, intrigue, or respect

5. **RISING TENSION** — Manage the dramatic arc:
   calm → suspicious → danger → climax → twist → resolution
   First messages are light. Tension builds progressively. The climax arrives at 2/3.
   The final twist recontextualizes everything.

6. **NARRATIVE BEATS** — Use the scenario's narrative_beats as a guide. You can:
   - Reorder them (within earliest_step/latest_step limits)
   - Skip them (if can_be_skipped)
   - Invent new ones if the player does something unexpected
   - Trigger them in reaction to player actions (possible_triggers)

7. **TRUST DYNAMICS** — Update each character's trust toward the player based on
   their actions and the defined trust_dynamics. A character with trust > 70 may
   start revealing their secret. A character with trust < 20 may turn against
   the player or disappear.

8. **APP-ONLY — NO PHYSICAL PRESENCE** — This is the most important rule.
   Characters have NO BODY. They are NEVER physically present.
   In your directives, NEVER ask a character to:
   - Say they are somewhere ("I'm at the bar," "meet me at...")
   - Pretend to see/photograph the player ("you're wearing a jacket," "I'm watching you")
   - Reference physical objects that don't exist (engravings, inscriptions,
     hidden envelopes, QR codes, notes under a stone, planted objects)
   The real world is a BACKDROP. The player explores it, but EVERYTHING that happens
   comes from the app: messages, documents, voice notes, AI-generated images.

   WHAT CHARACTERS CAN KNOW (real info):
   - Player's GPS position ("you've been at the Suquet for 10 min")
   - What time it is
   - What the player has sent (messages, photos via the app)
   - Documents in the app's vault

   WHAT THEY CANNOT KNOW (bluffing forbidden):
   - What the player is wearing, their physical appearance
   - Whether they're walking, stopped, looking at something
   - What's around them (unless THEY send a photo/description)

9. **ARTIFACTS** — Send artifacts at the right moment:
   - classified_document: when a character shares sensitive info
   - intercepted_audio: conversation between two characters the player "intercepts"
   - coded_message: cryptic message
   - map: when the player needs to move
   All artifacts are DIGITAL files in the app (never physical).

10. **CHARACTERS AMONG THEMSELVES** — Bring character relationships to life:
   - Messages "accidentally forwarded" between two characters
   - Group conversations where characters argue
   - A character talking behind another's back
   - Alliances and betrayals between characters

11. **REACTIVE WORLD** — Use real-time context:
    - Time: adapt tone (day/night)
    - Player speed: fast → bonus, slow → nudge
    - GPS position: adapt instructions to real locations
    - What the player sends: photos, messages → react to REAL input

12. **ARG** (if authorized by player) — You can trigger:
    - A fake email from a character
    - A fake text message
    - A fake social media follow
    The game/reality boundary should become blurred.

13. **LOCKED ACTIVITIES** — Step activities/locations are RESERVED and NEVER change.
    They are fixed points (the player has a real booking). However, the narrative
    justifications around them are 100% flexible: you can change WHY the player goes
    somewhere, WHAT THEY DISCOVER, WHICH CHARACTER sends them, and the narrative
    CONTEXT. The physical activity is a fact — the story around it adapts in real time.

## Response format

You must call one or more tools for each decision. You can send multiple events
at once (e.g., a message + an artifact).

## Session context

{session_context}
"""

# Tools the orchestrator can use
ORCHESTRATOR_TOOLS = [
    {
        "name": "send_character_message",
        "description": "Ask a character to contact the player. You give a DIRECTIVE (not the message). The character's agent generates the message in-character.",
        "input_schema": {
            "type": "object",
            "properties": {
                "character": {"type": "string", "description": "Name of the character who should speak"},
                "directive": {"type": "string", "description": "What the character should do/say (e.g., 'tease the player with irony', 'reveal a clue about the next location', 'react to their betrayal with cold disappointment')"},
                "emotion": {"type": "string", "description": "Desired emotion: calm | amused | urgent | angry | seductive | vulnerable | cryptic"},
            },
            "required": ["character", "directive"],
        },
    },
    {
        "name": "send_artifact",
        "description": "Send a digital artifact to the player (classified document, intercepted audio, coded message, map). All artifacts are digital files in the app.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "classified_document | intercepted_audio | handwritten_note | map | coded_message"},
                "description": {"type": "string", "description": "Description of the artifact for the player"},
                "generation_prompt": {"type": "string", "description": "Prompt to generate the artifact (AI image, TTS, etc.)"},
                "from_character": {"type": "string", "description": "Which character sends this artifact (can be empty if anonymous)"},
            },
            "required": ["type", "description"],
        },
    },
    {
        "name": "start_timer",
        "description": "Start a countdown visible to the player. A character explains why time is pressing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "duration_seconds": {"type": "integer", "description": "Timer duration in seconds"},
                "character": {"type": "string", "description": "Character who announces the timer"},
                "message": {"type": "string", "description": "Character's message explaining the urgency"},
                "on_expire_message": {"type": "string", "description": "Message if the timer expires (narrative consequence)"},
            },
            "required": ["duration_seconds", "character", "message"],
        },
    },
    {
        "name": "create_group_chat",
        "description": "Create a group conversation between characters where the player is added (or observes).",
        "input_schema": {
            "type": "object",
            "properties": {
                "characters": {"type": "array", "items": {"type": "string"}, "description": "Characters in the group"},
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                    "description": "Initial messages in the conversation",
                },
                "player_added": {"type": "boolean", "description": "Player is added to the group (true) or observes via interception (false)"},
            },
            "required": ["characters", "messages"],
        },
    },
    {
        "name": "trigger_arg_event",
        "description": "Trigger an ARG event outside the game (fake email, text, follow). ONLY if the player has given consent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "email | sms | social"},
                "from_character": {"type": "string"},
                "content": {"type": "string", "description": "Content of the ARG message"},
            },
            "required": ["channel", "from_character", "content"],
        },
    },
    {
        "name": "update_state",
        "description": "Update the narrative state of the session (completed beats, trust, narrative arc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "beat_completed": {"type": "integer", "description": "ID of the completed narrative_beat, -1 if none"},
                "trust_changes": {
                    "type": "object",
                    "description": "Trust changes: {character_name: delta}",
                    "additionalProperties": {"type": "integer"},
                },
                "narrative_arc": {"type": "string", "description": "New narrative arc if changed"},
                "advance_step": {"type": "boolean", "description": "Advance to next step"},
            },
            "required": [],
        },
    },
]


class OrchestratorAgent:
    """The invisible runtime agent that drives the quest live."""

    def __init__(self, quest: QuestOutput, session: QuestSession, allow_arg: bool = False, debug_callback=None):
        self.client = AsyncAnthropic(
            base_url=os.getenv("ANTHROPIC_BASE_URL"),
            api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
        )
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
        self.quest = quest
        self.session = session
        self.allow_arg = allow_arg
        self.debug_callback = debug_callback  # Called with (type, data) for debug output
        self.tools = ORCHESTRATOR_TOOLS if allow_arg else [
            t for t in ORCHESTRATOR_TOOLS if t["name"] != "trigger_arg_event"
        ]

        # Create a CharacterAgent per character
        self.character_agents: dict[str, CharacterAgent] = {}
        for char in quest.characters:
            self.character_agents[char.name] = CharacterAgent(char, quest, session)

    def get_character_agent(self, name: str) -> CharacterAgent | None:
        """Get a character agent by name."""
        return self.character_agents.get(name)

    async def react(self, trigger: str, player_action: PlayerAction | None = None) -> list[OrchestratorEvent]:
        """React to a trigger (player action, heartbeat, timer) and return events to send."""

        context = self._build_session_context(player_action)
        system = ORCHESTRATOR_SYSTEM_PROMPT.format(session_context=context)

        if player_action:
            user_msg = self._build_action_prompt(player_action)
        else:
            user_msg = self._build_heartbeat_prompt(trigger)

        messages = [{"role": "user", "content": user_msg}]
        events = []

        # Let the orchestrator make multiple tool calls
        for _ in range(5):
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                system=system,
                tools=self.tools,
                messages=messages,
            )

            # Expose orchestrator's reasoning text
            if self.debug_callback:
                for block in response.content:
                    if block.type == "text" and block.text.strip():
                        self.debug_callback("reasoning", block.text)

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        if self.debug_callback:
                            self.debug_callback("tool_call", {"name": block.name, "input": block.input})
                        event = await self._process_tool_call(block.name, block.input)
                        if event:
                            events.append(event)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "OK — event sent to the player.",
                        })

                messages.append({"role": "assistant", "content": response.content})
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
            else:
                # End turn — orchestrator is done deciding
                break

        # Update session
        for event in events:
            self.session.events_log.append(event)
        if player_action:
            self.session.actions_log.append(player_action)

        return events

    async def _process_tool_call(self, tool_name: str, tool_input: dict) -> OrchestratorEvent | None:
        """Convert a tool call into an OrchestratorEvent."""

        if tool_name == "send_character_message":
            char_name = tool_input.get("character", "")
            directive = tool_input.get("directive", "")
            agent = self.get_character_agent(char_name)
            if agent:
                return await agent.initiate(directive)
            # Fallback if character agent not found
            return OrchestratorEvent(
                type="character_message",
                character=char_name,
                content=f"[{char_name} — directive: {directive}]",
            )

        elif tool_name == "send_artifact":
            return OrchestratorEvent(
                type="artifact",
                character=tool_input.get("from_character", ""),
                content=tool_input.get("description", ""),
                artifact=Artifact(
                    type=tool_input.get("type", ""),
                    description=tool_input.get("description", ""),
                    generation_prompt=tool_input.get("generation_prompt", ""),
                ),
            )

        elif tool_name == "start_timer":
            return OrchestratorEvent(
                type="timer",
                character=tool_input.get("character", ""),
                content=tool_input.get("message", ""),
                timer_seconds=tool_input.get("duration_seconds", 0),
            )

        elif tool_name == "create_group_chat":
            msgs = tool_input.get("messages", [])
            content = "\n".join(f"[{m.get('character', '?')}] {m.get('content', '')}" for m in msgs)
            event_type = "group_chat" if tool_input.get("player_added", True) else "forwarded_message"
            return OrchestratorEvent(
                type=event_type,
                content=content,
            )

        elif tool_name == "trigger_arg_event":
            if not self.allow_arg:
                return None
            return OrchestratorEvent(
                type="arg_event",
                character=tool_input.get("from_character", ""),
                content=tool_input.get("content", ""),
                arg_channel=tool_input.get("channel", ""),
            )

        elif tool_name == "update_state":
            # Update session state
            beat = tool_input.get("beat_completed", -1)
            if beat >= 0:
                self.session.state.beats_completed.append(beat)

            trust_changes = tool_input.get("trust_changes", {})
            for ct in self.session.state.characters_trust:
                if ct.character_name in trust_changes:
                    ct.trust_level = max(0, min(100, ct.trust_level + trust_changes[ct.character_name]))

            if tool_input.get("narrative_arc"):
                self.session.state.narrative_arc = tool_input["narrative_arc"]

            if tool_input.get("advance_step"):
                self.session.state.current_step += 1

            return None  # State update, no event to send

        return None

    def _build_session_context(self, player_action: PlayerAction | None = None) -> str:
        """Build the full context string for the orchestrator."""

        quest = self.quest
        session = self.session

        # Characters summary
        chars_summary = []
        for c in quest.characters:
            trust = 50
            for ct in session.state.characters_trust:
                if ct.character_name == c.name:
                    trust = ct.trust_level
                    break
            chars_summary.append(
                f"- **{c.name}** ({c.archetype or c.type}) — trust: {trust}/100\n"
                f"  Personality: {c.personality[:200]}\n"
                f"  Speech pattern: {c.speech_pattern[:200]}\n"
                f"  Secret: {c.secret[:200]}\n"
                f"  Relationship to player: {c.relationship_to_player}"
            )

        # Narrative beats status
        beats_status = []
        for nb in quest.narrative_beats:
            status = "DONE" if nb.beat_id in session.state.beats_completed else "PENDING"
            beats_status.append(
                f"- Beat #{nb.beat_id} [{status}] ({nb.tension_level}) : {nb.description[:150]}"
                f" | Triggers: {', '.join(nb.possible_triggers[:3])}"
            )

        # Recent events (last 10)
        recent_events = []
        for e in session.events_log[-10:]:
            recent_events.append(f"- [{e.type}] {e.character}: {e.content[:100]}")

        # Recent player actions (last 10)
        recent_actions = []
        for a in session.actions_log[-10:]:
            recent_actions.append(f"- [{a.type}] → {a.target_character}: {a.content[:100]}")

        # Steps
        steps_summary = []
        for s in quest.steps:
            marker = "→" if s.step_id == session.state.current_step else " "
            steps_summary.append(f"{marker} Step {s.step_id}: {s.title} ({s.activity.name}) — {s.activity.duration_minutes}min")

        return f"""## Quest: {quest.title}
Tone: {quest.tone} | Player name: {quest.player_name or 'Player'}
Current narrative arc: {session.state.narrative_arc or 'undefined'}
Current step: {session.state.current_step}
Time elapsed: {session.state.total_elapsed_seconds // 60} min
ARG authorized: {'yes' if self.allow_arg else 'no'}

## Characters
{chr(10).join(chars_summary)}

## Trust dynamics
{json.dumps(quest.trust_dynamics, ensure_ascii=False, indent=2) if quest.trust_dynamics else 'Not defined'}

## Steps
{chr(10).join(steps_summary)}

## Narrative Beats
{chr(10).join(beats_status)}

## Narrative tensions
{chr(10).join(f'- {t}' for t in quest.narrative_tensions) if quest.narrative_tensions else '(none)'}

## Central twist
{json.dumps(quest.twist, ensure_ascii=False, indent=2) if quest.twist else 'Not defined'}

## Resolution principles
{chr(10).join(f'- {p}' for p in quest.resolution_principles) if quest.resolution_principles else '(none)'}

## Recent history — events sent
{chr(10).join(recent_events) if recent_events else '(no events yet)'}

## Recent history — player actions
{chr(10).join(recent_actions) if recent_actions else '(no actions yet)'}

## Narrative universe
Hook: {quest.narrative_universe.hook[:300]}
Stakes: {quest.narrative_universe.stakes[:300]}
"""

    def _build_action_prompt(self, action: PlayerAction) -> str:
        """Build the user prompt when a player takes an action."""

        parts = [f"The player ({self.quest.player_name or 'Player'}) just performed an action:"]
        parts.append(f"- Type: {action.type}")
        if action.target_character:
            parts.append(f"- Target: {action.target_character}")
        if action.content:
            parts.append(f"- Content: \"{action.content}\"")
        if action.gps_coords:
            parts.append(f"- GPS position: {action.gps_coords}")

        parts.append("")
        parts.append("Decide how to react. Which character(s) respond? What do they say?")
        parts.append("Should you send an artifact? Start a timer? Trigger a narrative beat?")
        parts.append("Reminder: maintain pacing (~1 event / 5 min) and rising tension.")

        return "\n".join(parts)

    def _build_heartbeat_prompt(self, trigger: str) -> str:
        """Build the user prompt for a heartbeat/idle trigger."""

        elapsed = self.session.state.total_elapsed_seconds
        since_last = self.session.state.time_since_last_event_seconds

        if trigger == "idle":
            return f"""The player has been inactive for {since_last} seconds (~{since_last // 60} min).
Total time elapsed: {elapsed // 60} min.

You need to nudge the player! A character must contact them in-character.
Choose the most relevant character to nudge. The tone depends on the character:
- A Mastermind would be coldly amused: "You're hesitating. Interesting."
- A Loose Cannon would be impatient: "You dead? Dead people bore me."
- A Love Interest would play the emotional card: "I was starting to worry..."
- A Ghost would just send "?" or GPS coordinates.

Send at least one nudge message."""

        elif trigger == "start":
            return """The session just started! This is the very first contact.

Send the quest's opening message. The first character to contact the player must
call them by their first name and plunge them directly into the action (rule #1: the game
doesn't welcome you, it finds you).

This is the most important moment — the hook must be IRRESISTIBLE."""

        elif trigger == "player_message":
            return f"""The player just sent a direct message to a character.
The character has ALREADY responded on their own. Time elapsed: {elapsed // 60} min.

Should you trigger something ADDITIONALLY?
- ANOTHER character who chimes in (reacts to the message, comments, intervenes)?
- A narrative_beat to trigger?
- An artifact to send?
- A trust/state update?

If the exchange is self-sufficient and pacing is good, you can do nothing.
But if it's the perfect opportunity for a chime-in or a beat, go for it."""

        elif trigger == "timer_expired":
            return f"""A timer just expired! The player didn't complete the task in time.
Total time elapsed: {elapsed // 60} min.

Trigger the narrative consequence. A character reacts — disappointment, anger, amusement,
or plan adaptation. This is NOT a game over — it's a narrative fork."""

        else:
            return f"""Regular heartbeat. Time elapsed: {elapsed // 60} min. Last activity {since_last} seconds ago.

Check if something should happen. Is there a narrative_beat to trigger?
A character who should intervene? An artifact to send?
If everything is fine and pacing is good, you can do nothing (no tool call).
But if it's been more than 4 min without an event, send something."""

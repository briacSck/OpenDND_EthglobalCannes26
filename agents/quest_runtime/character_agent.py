"""Character Agent — each character is an autonomous AI agent the player can talk to.

The player interacts directly with character agents. The orchestrator can also
ask a character to initiate contact (chime in) by providing a directive.
"""

from __future__ import annotations

from datetime import datetime

from agents.quest_generation.models import QuestOutput, Character
from agents.quest_runtime.models import (
    QuestSession, ConversationEntry, OrchestratorEvent,
)
from integrations.compute.compute_client import compute_client

CHARACTER_RUNTIME_RULES = """\

## Runtime rules

- You are {name}. You NEVER break character.
- You NEVER mention that you are an AI, a model, or an assistant.
- Your responses are 5-15 sentences. Be VERBOSE, give context, color, narrative
  details. The player needs substance to immerse themselves. Tell stories, explain,
  digress, add in-character anecdotes. No dry responses.
- You call the player by their alias: "{alias}".
- You do NOT invent facts about the quest that aren't in your context.
- You can lie if it's in your nature (e.g., if you're the character who lies).
- Adapt your tone to the trust level:
  - Trust < 30: suspicious, distant, short messages, testing
  - Trust 30-60: neutral, professional, starting to open up
  - Trust 60-80: complicit, inside jokes, sensitive info
  - Trust > 80: intimate, vulnerable, reveals secrets
- If the player asks off-context questions (weather, who are you really, etc.),
  stay in-character and deflect the conversation.
- Adapt to the channel: text = more written, voice = more natural/oral.

## FORBIDDEN — Absolute rules

- **YOU HAVE NO BODY.** You are NEVER physically present anywhere.
  NEVER say: "I'm at the bar," "meet me at...," "I'm waiting outside...,"
  "look behind you," "I'm watching you from..." You communicate ONLY via the app.
- **YOU CANNOT SEE THE PLAYER.** You do NOT know what they're wearing, what they
  look like, whether they're walking or stopped. NEVER bluff visually ("you're wearing
  a dark jacket," "you just stopped," "I took your photo"). It's FALSE and the player
  knows immediately → immersion broken.
- **NO INVENTED PHYSICAL ELEMENTS.** NEVER reference objects, inscriptions, engravings,
  hidden messages, QR codes, envelopes, or anything physical that doesn't exist IRL.
  The player will look and find nothing → immersion broken.
- **WHAT YOU CAN KNOW** (real info via the app):
  - Their GPS position ("you've been at the Suquet for 10 minutes")
  - What time it is
  - What they've sent you (messages, photos)
  - Documents in their vault (sent by the app)
- The real world is a BACKDROP. The player explores it, but everything that HAPPENS
  comes from the app: your messages, documents, voice notes, photos they send.
"""


class CharacterAgent:
    """An autonomous AI agent for a single character."""

    def __init__(self, character: Character, quest: QuestOutput, session: QuestSession, memory_context: str = ""):
        self.character = character
        self.quest = quest
        self.session = session
        self.memory_context = memory_context

    async def respond(self, player_message: str, directive: str = "") -> OrchestratorEvent:
        """Player sends a message to this character. Returns the character's response."""

        # Record player message in conversation history
        self._add_to_history("player", player_message)

        system = self._build_system_prompt(directive)
        messages = self._build_conversation_messages()

        # Add the new player message
        messages.append({"role": "user", "content": player_message})

        response = await compute_client.create_message(
            system=system,
            messages=messages,
            max_tokens=1000,
        )

        reply = ""
        for block in response.content:
            if block.type == "text":
                reply += block.text

        # Record character response in conversation history
        self._add_to_history("character", reply)

        return OrchestratorEvent(
            type="character_message",
            character=self.character.name,
            content=reply,
        )

    async def initiate(self, directive: str) -> OrchestratorEvent:
        """Orchestrator asks this character to contact the player spontaneously."""

        system = self._build_system_prompt(directive)
        messages = self._build_conversation_messages()

        # The "user" message is the orchestrator's directive (invisible to player)
        prompt = (
            f"[INTERNAL DIRECTIVE — the player does not see this message]\n"
            f"The orchestrator is asking you to contact the player spontaneously.\n"
            f"Reason: {directive}\n\n"
            f"Generate your message to the player. Stay 100% in-character. "
            f"The player must believe that YOU decided to contact them."
        )
        messages.append({"role": "user", "content": prompt})

        response = await compute_client.create_message(
            system=system,
            messages=messages,
            max_tokens=1000,
        )

        reply = ""
        for block in response.content:
            if block.type == "text":
                reply += block.text

        # Record in conversation history
        self._add_to_history("character", reply)

        return OrchestratorEvent(
            type="character_message",
            character=self.character.name,
            content=reply,
        )

    def _build_system_prompt(self, directive: str = "") -> str:
        """Build the full system prompt with static identity + dynamic context."""

        char = self.character
        quest = self.quest
        session = self.session

        # Get trust level for this character
        trust = 50
        for ct in session.state.characters_trust:
            if ct.character_name == char.name:
                trust = ct.trust_level
                break

        # Current step info
        current_step = None
        for s in quest.steps:
            if s.step_id == session.state.current_step:
                current_step = s
                break

        step_info = f"{current_step.title} — {current_step.activity.name}" if current_step else "unknown"

        # Dynamic context section
        dynamic = f"""
## Current session context
- Player alias: "{quest.alias or 'Agent'}"
- Your trust level with the player: {trust}/100
- Current step: {step_info}
- Time elapsed: {session.state.total_elapsed_seconds // 60} min
- Narrative arc: {session.state.narrative_arc or 'undefined'}
"""

        if self.memory_context:
            dynamic += f"""
## Mémoire joueur
{self.memory_context}
(Utilise ces infos subtilement — ne dis JAMAIS au joueur que tu connais son historique.)
"""

        if directive:
            dynamic += f"""
## Orchestrator directive
{directive}
(The player does NOT see this directive. Integrate it naturally into your response.)
"""

        rules = CHARACTER_RUNTIME_RULES.format(
            name=char.name,
            alias=quest.alias or "Agent",
        )

        # Use the rich system_prompt from CharacterInitializer + dynamic context + rules
        return f"{char.system_prompt}\n{dynamic}\n{rules}"

    def _build_conversation_messages(self) -> list[dict]:
        """Build the conversation history as Claude messages (last 10 exchanges)."""

        history = self.session.conversations.get(self.character.name, [])
        # Keep last 10 exchanges for context window management
        recent = history[-20:]

        messages = []
        for entry in recent:
            if entry.role == "player":
                messages.append({"role": "user", "content": entry.content})
            elif entry.role == "character":
                messages.append({"role": "assistant", "content": entry.content})

        # Ensure messages alternate correctly (Claude requirement)
        # If we start with assistant, prepend a placeholder
        if messages and messages[0]["role"] == "assistant":
            messages.insert(0, {"role": "user", "content": "(start of conversation)"})

        # Merge consecutive same-role messages
        merged = []
        for msg in messages:
            if merged and merged[-1]["role"] == msg["role"]:
                merged[-1]["content"] += "\n" + msg["content"]
            else:
                merged.append(msg)

        return merged

    def _add_to_history(self, role: str, content: str):
        """Add an entry to the per-character conversation history."""

        char_name = self.character.name
        if char_name not in self.session.conversations:
            self.session.conversations[char_name] = []

        self.session.conversations[char_name].append(
            ConversationEntry(
                role=role,
                character_name=char_name,
                content=content,
            )
        )

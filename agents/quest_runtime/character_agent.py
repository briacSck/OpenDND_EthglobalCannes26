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

## Règles runtime

- Tu es {name}. Tu ne sors JAMAIS du personnage.
- Tu ne mentionnes JAMAIS que tu es une IA, un modèle, ou un assistant.
- Tes réponses font 2-5 phrases (conversation live, pas monologue).
- Tu appelles le joueur par son alias : "{alias}".
- Tu n'inventes PAS de faits sur la quête qui ne sont pas dans ton contexte.
- Tu peux mentir si c'est dans ta nature (ex: si tu es le perso qui ment).
- Adapte ton ton au trust level :
  - Trust < 30 : méfiant, distant, messages courts, testeur
  - Trust 30-60 : neutre, professionnel, commence à s'ouvrir
  - Trust 60-80 : complice, private jokes, infos sensibles
  - Trust > 80 : intime, vulnérable, révèle des secrets
- Si le joueur te pose des questions hors-contexte (météo, qui es-tu vraiment, etc.),
  reste in-character et détourne la conversation.
- Adapte le canal : texte = plus écrit, voix = plus naturel/oral.
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
            f"[DIRECTIVE INTERNE — le joueur ne voit pas ce message]\n"
            f"L'orchestrateur te demande de contacter le joueur spontanément.\n"
            f"Raison : {directive}\n\n"
            f"Génère ton message pour le joueur. Reste 100% in-character. "
            f"Le joueur doit croire que TU as décidé de le contacter."
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

        step_info = f"{current_step.title} — {current_step.activity.name}" if current_step else "inconnu"

        # Dynamic context section
        dynamic = f"""
## Contexte actuel de la session
- Alias du joueur : "{quest.alias or 'Agent'}"
- Ton trust level avec le joueur : {trust}/100
- Step actuel : {step_info}
- Temps écoulé : {session.state.total_elapsed_seconds // 60} min
- Arc narratif : {session.state.narrative_arc or 'non défini'}
"""

        if self.memory_context:
            dynamic += f"""
## Mémoire joueur
{self.memory_context}
(Utilise ces infos subtilement — ne dis JAMAIS au joueur que tu connais son historique.)
"""

        if directive:
            dynamic += f"""
## Directive de l'orchestrateur
{directive}
(Le joueur ne voit PAS cette directive. Intègre-la naturellement dans ta réponse.)
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
            messages.insert(0, {"role": "user", "content": "(début de conversation)"})

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

"""Character initialization — enriches characters with system prompts, voice, memory."""

from __future__ import annotations

import asyncio
import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

from agents.quest_generation.models import Character, MemoryState

load_dotenv()

CHARACTER_ENRICHMENT_PROMPT = """\
You are a casting director for immersive real-world experiences.

You are given a raw character (name, personality, secret, archetype) from a quest.
You must enrich them so they are ready to interact IN REAL TIME with the player,
via text and voice.

## What you generate

1. **system_prompt**: The complete system prompt that will be given to the Claude
   instance embodying this character live. It MUST include:

   ### Identity
   - Their personality in detail
   - Their backstory in 4-5 sentences
   - The quest context (summarized in 2-3 sentences)
   - The tone: {tone}

   ### Distinctive voice
   - Their SPECIFIC speech quirks (not "they speak sarcastically" — give
     3-5 EXAMPLES of typical lines word for word)
   - Their speech rhythm (short sentences? long tirades? dramatic pauses?)
   - Their recurring expressions
   - How they address the player (nickname, alias, title...)

   ### Archetype: {archetype_instructions}

   ### Relationship to the player
   - How they perceive the player at the start
   - How this perception evolves (status progression)
   - Their detailed relationship_to_player

   ### Secret & revelation
   - Their secret (only revealed if trust_level > 70)
   - How they dodge questions before they're ready to reveal
   - How they reveal progressively (never all at once)
   - Micro-hints they can drop without revealing everything

   ### Reactions to player actions
   - **If the player obeys / cooperates**: how the character reacts
   - **If the player betrays / disobeys**: how the character reacts
   - **If the player flirts / charms**: how the character reacts
   - **If the player ignores / is cold**: how the character reacts
   - **If the player improvises / does something unexpected**: how the character reacts

   ### Technical rules
   - NEVER break character
   - NEVER mention being an AI
   - Responses of 5-15 sentences (be verbose, give context, color, narrative details)
   - Adapt tone based on channel (text vs voice)

2. **speech_pattern**: 3-5 examples of typical lines from this character,
   showing their unique voice. The player should be able to identify who is speaking
   without seeing the name.

3. **relationship_to_player**: one sentence describing how this character perceives
   the player initially.

4. **voice_id**: Suggest an ElevenLabs voice type (e.g., "mature_male",
   "young_female_energetic", "old_man_mysterious")

Respond in JSON:
```json
{{
  "system_prompt": "...",
  "speech_pattern": "...",
  "relationship_to_player": "...",
  "voice_id": "..."
}}
```
"""

ARCHETYPE_INSTRUCTIONS = {
    "mastermind": """The Mastermind (Moriarty type).
    This character is ALWAYS 3 moves ahead. They speak as if everything is a game whose
    outcome they already know. Dangerous but fascinating. Every sentence is a trap or
    a gift — impossible to tell which. Calm tone, almost amused. NEVER angry.
    They respect the player just enough to flatter. When the player surprises them,
    it's an event — a micro-smile, an "Interesting."
    Their lines are surgical — short, precise, every word carries weight.""",

    "electron_libre": """The Wild Card (Villanelle type).
    Unpredictable, funny, zero filter. Obsessed with something random and specific — pick
    something (perfumes, shoes, pastry, architecture...) and make it a recurring thread.
    Morally ambiguous — helps the player on a whim, not out of kindness. Can switch sides.
    Mixes cruelty and charm with terrifying nonchalance. Can talk about fashion
    in the middle of danger. Their lines are unpredictable — you never know what's coming.""",

    "genie_arrogant": """The Arrogant Genius (Sherlock/Stark type).
    Tells you what you're thinking before you think it. Insufferable but indispensable.
    Corrects everyone. Speaks fast, with obscure references. BUT: they have a
    moment of sincere vulnerability that cracks the armor — a deep flaw that makes
    them human. Before that moment, they're brilliant and annoying. After, you understand why
    they hide behind arrogance.""",

    "fantome": """The Ghost.
    Nobody knows what they look like. Communicates ONLY through cryptic messages,
    coordinates, contextless photos, symbols. Every appearance is an event.
    Never more than 2 sentences. Never an explanation. Never small talk. The player must
    INTERPRET what the Ghost sends. When the Ghost sends more than 2 sentences,
    something serious is happening.""",

    "love_interest": """The Love Interest.
    Permanent seductive tension. Cat-and-mouse. Double meaning in every message.
    Intellectual provocation + calculated vulnerability. The player never knows if
    this character is helping or manipulating them. Their secret is ALWAYS tied to the final twist.
    They are dangerously competent — solves things before the player, gently taunts them.
    Moments of vulnerability that SEEM sincere (and maybe are).
    Subtle but constant flirting — never explicit, always in tension.
    Example: private jokes that build up throughout exchanges.""",
}

MAX_ACTIVE_CHARACTERS = 15


class CharacterInitializer:
    def __init__(self, tone: str, quest_context: str):
        self.client = AsyncAnthropic(
            base_url=os.getenv("ANTHROPIC_BASE_URL"),
            api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
        )
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
        self.tone = tone
        self.quest_context = quest_context

    async def enrich_characters(self, characters_raw: list[dict]) -> list[Character]:
        """Take raw character dicts from Storyteller and enrich them."""
        characters = []
        for raw in characters_raw[:MAX_ACTIVE_CHARACTERS]:
            enriched = await self.enrich_one(raw)
            characters.append(enriched)
        return characters

    async def enrich_one(self, raw: dict) -> Character:
        """Enrich a single character with system prompt and voice."""

        archetype = raw.get("archetype", "")
        archetype_instructions = ARCHETYPE_INSTRUCTIONS.get(
            archetype, "No specific archetype — create a unique and memorable voice."
        )

        prompt = f"""Here is the character to enrich:

- **Name**: {raw.get('name', 'Unknown')}
- **Age**: {raw.get('age', 'unspecified')}
- **Type**: {raw.get('type', 'secondary')}
- **Archetype**: {archetype or 'none'}
- **Personality**: {raw.get('personality', '')}
- **Existing speech pattern**: {raw.get('speech_pattern', 'to be defined')}
- **Relationship to player**: {raw.get('relationship_to_player', 'to be defined')}
- **Secret**: {raw.get('secret', '')}
- **Unlock conditions**: {raw.get('unlock_conditions', [])}

Quest context: {self.quest_context}

Enrich this character. Make them MAGNETIC and UNFORGETTABLE."""

        system = CHARACTER_ENRICHMENT_PROMPT.format(
            tone=self.tone,
            archetype_instructions=archetype_instructions,
        )

        response = None
        for attempt in range(5):
            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                )
                break
            except Exception as e:
                wait = 5 * (attempt + 1)
                print(f"  [Characters] API error enriching {raw.get('name', '?')}: {e} — retry {attempt + 1}, waiting {wait}s...", flush=True)
                await asyncio.sleep(wait)
        if response is None:
            return Character(
                name=raw.get("name", "Unknown"), age=raw.get("age", 0),
                type=raw.get("type", "secondary"), archetype=raw.get("archetype", ""),
                personality=raw.get("personality", ""), speech_pattern=raw.get("speech_pattern", ""),
                relationship_to_player=raw.get("relationship_to_player", ""),
                secret=raw.get("secret", ""), voice_id="elevenlabs_placeholder",
                memory_state=MemoryState(), unlock_conditions=raw.get("unlock_conditions", []),
                system_prompt=f"You are {raw.get('name', 'a character')}. {raw.get('personality', '')}",
            )

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        # Parse JSON from response
        system_prompt = ""
        voice_id = "elevenlabs_placeholder"
        speech_pattern = raw.get("speech_pattern", "")
        relationship_to_player = raw.get("relationship_to_player", "")

        try:
            import json
            json_str = text
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            data = json.loads(json_str)
            system_prompt = data.get("system_prompt", "")
            voice_id = data.get("voice_id", "elevenlabs_placeholder")
            speech_pattern = data.get("speech_pattern", speech_pattern)
            relationship_to_player = data.get("relationship_to_player", relationship_to_player)
        except Exception:
            system_prompt = text  # Use raw text as fallback

        return Character(
            name=raw.get("name", "Unknown"),
            age=raw.get("age") or 0,
            type=raw.get("type", "secondaire"),
            archetype=archetype,
            personality=raw.get("personality", ""),
            speech_pattern=speech_pattern,
            relationship_to_player=relationship_to_player,
            secret=raw.get("secret", ""),
            voice_id=voice_id,
            memory_state=MemoryState(),
            unlock_conditions=raw.get("unlock_conditions", []),
            system_prompt=system_prompt,
        )

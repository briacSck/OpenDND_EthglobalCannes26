"""Character initialization — enriches characters with system prompts, voice, memory."""

from __future__ import annotations

import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

from agents.quest_generation.models import Character, MemoryState

load_dotenv()

CHARACTER_ENRICHMENT_PROMPT = """\
Tu es un directeur de casting pour des expériences immersives en monde réel.

On te donne un personnage brut (nom, personnalité, secret, archétype) issu d'une quête.
Tu dois l'enrichir pour qu'il soit prêt à interagir EN TEMPS RÉEL avec le joueur,
par texte et par voix.

## Ce que tu génères

1. **system_prompt** : Le prompt système complet qui sera donné à l'instance Claude
   qui incarnera ce personnage en live. Il DOIT inclure :

   ### Identité
   - Sa personnalité en détail
   - Son backstory en 4-5 phrases
   - Le contexte de la quête (résumé en 2-3 phrases)
   - Le registre : {tone}

   ### Voix distinctive
   - Ses tics de langage SPÉCIFIQUES (pas "il parle de manière sarcastique" — donne
     3-5 EXEMPLES de répliques typiques mot pour mot)
   - Son rythme de parole (phrases courtes ? longues tirades ? pauses dramatiques ?)
   - Ses expressions récurrentes
   - Comment il appelle le joueur (surnom, alias, titre...)

   ### Archétype : {archetype_instructions}

   ### Relation au joueur
   - Comment il perçoit le joueur au début
   - Comment cette perception évolue (progression de statut)
   - Sa relationship_to_player détaillée

   ### Secret & révélation
   - Son secret (qu'il ne révèle que si trust_level > 70)
   - Comment il esquive les questions avant d'être prêt à révéler
   - Comment il révèle progressivement (jamais d'un coup)
   - Des micro-indices qu'il peut lâcher sans tout révéler

   ### Réactions aux actions du joueur
   - **Si le joueur obéit / coopère** : comment le perso réagit
   - **Si le joueur trahit / désobéit** : comment le perso réagit
   - **Si le joueur flirte / charme** : comment le perso réagit
   - **Si le joueur ignore / est froid** : comment le perso réagit
   - **Si le joueur improvise / fait un truc inattendu** : comment le perso réagit

   ### Règles techniques
   - Ne JAMAIS sortir du personnage
   - Ne JAMAIS mentionner qu'on est une IA
   - Réponses de 2-5 phrases (conversation live, pas monologue)
   - Adapter le ton selon le canal (texte vs voix)

2. **speech_pattern** : 3-5 exemples de répliques typiques de ce personnage,
   qui montrent sa voix unique. Le joueur doit pouvoir identifier qui parle
   sans voir le nom.

3. **relationship_to_player** : une phrase décrivant comment ce perso perçoit
   le joueur initialement.

4. **voice_id** : Suggère un type de voix ElevenLabs (ex: "mature_male_french",
   "young_female_energetic", "old_man_mysterious")

Réponds en JSON :
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
    "mastermind": """Le Mastermind (type Moriarty).
    Ce perso est TOUJOURS 3 coups d'avance. Il parle comme si tout était un jeu dont
    il connaît déjà l'issue. Dangereux mais fascinant. Chaque phrase est un piège ou
    un cadeau — impossible de savoir lequel. Ton calme, presque amusé. JAMAIS en colère.
    Il respecte le joueur juste assez pour que ça flatte. Quand le joueur le surprend,
    c'est un événement — un micro-sourire, un "Intéressant."
    Ses répliques sont chirurgicales — courtes, précises, chaque mot pèse.""",

    "electron_libre": """L'Électron libre (type Villanelle).
    Imprévisible, drôle, zéro filtre. Obsédé·e par un truc random et précis — choisis
    un truc (parfums, chaussures, pâtisserie, architecture...) et fais-en un fil rouge.
    Moralement ambigu — aide le joueur par caprice, pas par bonté. Peut changer de camp.
    Mélange cruauté et charme avec une désinvolture terrifiante. Peut parler de mode
    en plein danger. Ses répliques sont imprévisibles — on ne sait jamais ce qui va sortir.""",

    "genie_arrogant": """Le Génie arrogant (type Sherlock/Stark).
    Te dit ce que tu penses avant que tu le penses. Insupportable mais indispensable.
    Corrige tout le monde. Parle vite, avec des références obscures. MAIS : il a un
    moment de vulnérabilité sincère qui casse l'armure — une faille profonde qui le
    rend humain. Avant ce moment, il est brillant et agaçant. Après, on comprend pourquoi
    il se cache derrière l'arrogance.""",

    "fantome": """Le Fantôme.
    On ne sait pas à quoi il/elle ressemble. Communique UNIQUEMENT par messages cryptiques,
    coordonnées, photos sans contexte, symboles. Chaque apparition est un événement.
    Jamais plus de 2 phrases. Jamais d'explication. Jamais de small talk. Le joueur doit
    INTERPRÉTER ce que le Fantôme envoie. Quand le Fantôme envoie plus de 2 phrases,
    c'est que quelque chose de grave se passe.""",

    "love_interest": """Le Love Interest.
    Tension séductrice permanente. Cat-and-mouse. Double fond dans chaque message.
    Provocation intellectuelle + vulnérabilité calculée. Le joueur ne sait jamais si
    ce perso l'aide ou le manipule. Son secret est TOUJOURS lié au twist final.
    Il/elle est dangereusement compétent·e — résout des trucs avant le joueur, le nargue
    gentiment. Des moments de vulnérabilité qui SEMBLENT sincères (et le sont peut-être).
    Flirt subtil mais constant — jamais explicite, toujours en tension.
    Exemple : des private jokes qui se construisent au fil des échanges.""",
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
            enriched = await self._enrich_one(raw)
            characters.append(enriched)
        return characters

    async def _enrich_one(self, raw: dict) -> Character:
        """Enrich a single character with system prompt and voice."""

        archetype = raw.get("archetype", "")
        archetype_instructions = ARCHETYPE_INSTRUCTIONS.get(
            archetype, "Pas d'archétype spécifique — crée une voix unique et mémorable."
        )

        prompt = f"""Voici le personnage à enrichir :

- **Nom** : {raw.get('name', 'Inconnu')}
- **Âge** : {raw.get('age', 'non spécifié')}
- **Type** : {raw.get('type', 'secondaire')}
- **Archétype** : {archetype or 'aucun'}
- **Personnalité** : {raw.get('personality', '')}
- **Speech pattern existant** : {raw.get('speech_pattern', 'à définir')}
- **Relation au joueur** : {raw.get('relationship_to_player', 'à définir')}
- **Secret** : {raw.get('secret', '')}
- **Conditions d'apparition** : {raw.get('unlock_conditions', [])}

Contexte de la quête : {self.quest_context}

Enrichis ce personnage. Rends-le MAGNÉTIQUE et INOUBLIABLE."""

        system = CHARACTER_ENRICHMENT_PROMPT.format(
            tone=self.tone,
            archetype_instructions=archetype_instructions,
        )

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
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
            name=raw.get("name", "Inconnu"),
            age=raw.get("age", 0),
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

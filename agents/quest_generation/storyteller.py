"""Storyteller Agent — creates the narrative, dialogues with Curator."""

from __future__ import annotations

import json
import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

from agents.city_research.models import CityContext
from agents.quest_generation.models import QuestRequest
from agents.quest_generation.curator import CuratorAgent
from agents.quest_generation.prompts import build_storyteller_prompt

load_dotenv()


def log(msg: str):
    print(msg, flush=True)


MAX_DIALOGUE_TURNS = 3

# Tool the Storyteller uses to ask the Curator for activities
ASK_CURATOR_TOOL = {
    "name": "ask_curator",
    "description": "Demande au Curator des activités réelles. Décris ce dont tu as besoin narrativement — le Curator te répondra avec ce qui existe vraiment, les prix, et le budget restant.",
    "input_schema": {
        "type": "object",
        "properties": {
            "request": {
                "type": "string",
                "description": "Ta demande au Curator : de quels types de lieux/activités tu as besoin, contraintes de zone, ambiance, prix, etc.",
            }
        },
        "required": ["request"],
    },
}

# Tool the Storyteller uses to submit the final quest
SUBMIT_QUEST_TOOL = {
    "name": "submit_quest",
    "description": "Soumets la quête finale complète. Appelle cet outil quand ta trame est prête avec tous les steps, personnages, et le decision tree.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "alias": {"type": "string", "description": "Nom de code du joueur — les persos l'appellent par cet alias"},
            "narrative_universe": {
                "type": "object",
                "properties": {
                    "hook": {"type": "string", "description": "Le premier message — irrésistible, présuppose un rôle existant"},
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
                        "type": {"type": "string", "description": "principal | secondaire"},
                        "archetype": {"type": "string", "description": "mastermind | electron_libre | genie_arrogant | fantome | love_interest | vide si pas applicable"},
                        "personality": {"type": "string"},
                        "speech_pattern": {"type": "string", "description": "3+ exemples de répliques typiques de ce perso"},
                        "relationship_to_player": {"type": "string", "description": "Comment ce perso perçoit le joueur initialement"},
                        "secret": {"type": "string"},
                        "unlock_conditions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name", "personality", "secret"],
                },
            },
            "steps": {
                "type": "array",
                "items": {
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
                                    "trigger": {"type": "string"},
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
                            },
                        },
                        "blockchain_event": {"type": "string"},
                        "unlock_message": {"type": "string"},
                        "skill_xp": {"type": "integer"},
                    },
                    "required": ["step_id", "title", "activity", "narrative_intro", "instruction"],
                },
            },
            "decision_tree": {
                "type": "object",
                "properties": {
                    "decisions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "step_id": {"type": "integer"},
                                "prompt": {"type": "string"},
                                "options": {"type": "array", "items": {"type": "string"}},
                                "consequence": {"type": "string"},
                            },
                        },
                    },
                    "endings": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "condition": {"type": "string"},
                                "narrative": {"type": "string"},
                                "reward": {"type": "string"},
                                "cost_eur": {"type": "number"},
                            },
                        },
                    },
                },
            },
            "narrative_beats": {
                "type": "array",
                "description": "Moments-clés flexibles que l'orchestrateur runtime placera dynamiquement",
                "items": {
                    "type": "object",
                    "properties": {
                        "beat_id": {"type": "integer"},
                        "description": {"type": "string", "description": "Ce qui se passe narrativement"},
                        "characters_involved": {"type": "array", "items": {"type": "string"}},
                        "earliest_step": {"type": "integer"},
                        "latest_step": {"type": "integer"},
                        "tension_level": {"type": "string", "description": "low | medium | high | climax"},
                        "can_be_skipped": {"type": "boolean"},
                        "possible_triggers": {"type": "array", "items": {"type": "string"}, "description": "Actions du joueur qui pourraient déclencher ce beat"},
                    },
                    "required": ["beat_id", "description", "characters_involved", "tension_level"],
                },
            },
            "possible_arcs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3 directions narratives possibles selon les choix du joueur",
            },
            "trust_dynamics": {
                "type": "object",
                "description": "Pour chaque perso, comment sa relation évolue : {nom_perso: {obey: +10, betray: -30, flirt: +5, ignore: -10}}",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "obey": {"type": "integer"},
                        "betray": {"type": "integer"},
                        "flirt": {"type": "integer"},
                        "ignore": {"type": "integer"},
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
        "required": ["title", "alias", "narrative_universe", "characters", "steps", "narrative_beats", "possible_arcs", "trust_dynamics", "decision_tree"],
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
        self.tools = [ASK_CURATOR_TOOL, SUBMIT_QUEST_TOOL]
        self.curator_iterations = 0

    async def generate(self) -> dict:
        """Run the Storyteller ↔ Curator dialogue and return the raw quest dict."""

        user_prompt = self._build_initial_prompt()
        messages = [{"role": "user", "content": user_prompt}]

        for i in range(MAX_DIALOGUE_TURNS + 3):  # extra margin for submit
            log(f"\n--- Storyteller iteration {i + 1} ---")

            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=16000,
                    system=self.system_prompt,
                    tools=self.tools,
                    messages=messages,
                )
            except Exception as e:
                log(f"  [Storyteller] API error: {e} — trimming context and retrying...")
                # Trim older curator exchanges to reduce context size
                if len(messages) > 3:
                    messages = [messages[0]] + messages[-2:]
                messages.append({
                    "role": "user",
                    "content": "L'appel précédent a échoué. Appelle submit_quest immédiatement avec la quête basée sur ce que tu as déjà.",
                })
                continue

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "text":
                        log(f"  [Storyteller] {block.text[:200]}...")
                    elif block.type == "tool_use":
                        if block.name == "submit_quest":
                            print("  [Storyteller] Quest submitted!")
                            self.curator_iterations = self.curator_iterations
                            return block.input

                        if block.name == "ask_curator":
                            self.curator_iterations += 1
                            log(f"  [Storyteller → Curator] Tour {self.curator_iterations}: {block.input['request'][:150]}...")
                            curator_response = await self.curator.respond(block.input["request"])
                            log(f"  [Curator → Storyteller] {curator_response[:200]}...")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": curator_response,
                            })

                messages.append({"role": "assistant", "content": response.content})
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "end_turn":
                # Nudge to submit
                for block in response.content:
                    if block.type == "text":
                        log(f"  [Storyteller] {block.text[:300]}")
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": "Ta trame est excellente. Maintenant appelle submit_quest avec la quête complète en JSON.",
                })

            elif response.stop_reason == "max_tokens":
                # Handle truncation
                messages.append({"role": "assistant", "content": response.content})
                dangling = [b.id for b in response.content if b.type == "tool_use"]
                if dangling:
                    dummies = [{"type": "tool_result", "tool_use_id": tid, "content": "[tronqué]"} for tid in dangling]
                    messages.append({"role": "user", "content": dummies + [
                        {"type": "text", "text": "Réponse tronquée. Appelle submit_quest immédiatement avec ce que tu as."}
                    ]})
                else:
                    messages.append({
                        "role": "user",
                        "content": "Réponse tronquée. Appelle submit_quest immédiatement.",
                    })

        raise RuntimeError("Storyteller did not submit after max iterations")

    async def revise(self, quest_raw: dict, feedback: list[dict]) -> dict:
        """Revise a quest based on Judge feedback."""

        feedback_text = "\n".join(
            f"- [{fb['agent']}] {fb['issue']} → {fb['instruction']}"
            for fb in feedback
        )

        messages = [
            {"role": "user", "content": f"""Voici la quête que tu as produite :

```json
{json.dumps(quest_raw, ensure_ascii=False, indent=2)[:12000]}
```

Le Judge a renvoyé ces feedbacks :

{feedback_text}

Corrige la quête en tenant compte de ces retours. Appelle submit_quest avec la version corrigée."""}
        ]

        for i in range(4):
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                system=self.system_prompt,
                tools=self.tools,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                for block in response.content:
                    if block.type == "tool_use" and block.name == "submit_quest":
                        return block.input
                    if block.type == "tool_use" and block.name == "ask_curator":
                        curator_response = await self.curator.respond(block.input["request"])
                        messages.append({"role": "assistant", "content": response.content})
                        messages.append({"role": "user", "content": [
                            {"type": "tool_result", "tool_use_id": block.id, "content": curator_response}
                        ]})
                        continue
                # If we got here, no submit — nudge
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": "Appelle submit_quest maintenant."})
            else:
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": "Appelle submit_quest avec la version corrigée."})

        raise RuntimeError("Storyteller revision did not produce a result")

    def _build_initial_prompt(self) -> str:
        # Build news section for high_stakes
        news_section = ""
        if self.request.tone == "high_stakes" and self.city_context.current_news:
            news_items = "\n".join(
                f"- **{n.name}** ({n.date}) — {n.summary} [Pertinence narrative : {n.relevance_for_narrative}]"
                for n in self.city_context.current_news
            )
            news_section = f"""
## Actualité & contexte géopolitique (ANCRAGE RÉEL)
Utilise ces faits réels vérifiables pour ancrer ta trame. Le joueur doit pouvoir
googler ces éléments et trouver de vrais articles.

{news_items}
"""

        return f"""Voici le contexte de la quête à créer :

## Demande du joueur
- **Skill** : {self.request.skill or 'exploration urbaine'}
- **Vibe** : {self.request.vibe}
- **Durée** : {self.request.duration}
- **Budget** : {self.request.budget}€
- **Lieu** : {self.request.location}
- **Difficulté** : {self.request.difficulty}
- **Joueurs** : {self.request.players}
- **Date/Heure** : {self.request.datetime}
- **Tone** : {self.request.tone}

## Essence de la ville
{self.city_context.city_description}

## Ce que tu sais déjà de la ville
- Quartier principal : {self.city_context.location.neighborhood}
- Météo : {self.city_context.location.weather}, {self.city_context.location.temperature}
- Transport : {self.city_context.transport.notes}
{news_section}
Commence par réfléchir à ta direction narrative, puis demande au Curator les
activités dont tu as besoin. Go !"""

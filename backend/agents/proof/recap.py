"""Quest recap generation — summarize a completed quest for the player."""

from __future__ import annotations

import json
import logging

from agents.quest_generation.models import QuestOutput
from agents.quest_runtime.models import QuestSession
from config import DEMO_MODE
from integrations.compute.compute_client import compute_client

logger = logging.getLogger(__name__)

# Imported here to avoid circular — QuestRecapResponse is defined in integration models
# but we return a dict and let the caller wrap it.

RECAP_SYSTEM = """\
Tu es un narrateur qui résume une quête immersive terminée.
On te donne le contexte de la quête et les événements majeurs.
Génère un récap engageant en JSON strict avec ces champs :
- narrative_summary : 3-5 phrases résumant l'aventure du joueur
- highlights : liste de 3-5 moments mémorables (strings)
- next_quest_teaser : 1 phrase d'accroche pour la prochaine quête
- grade : note A-F basée sur vitesse, trust, steps complétés

Réponds UNIQUEMENT avec du JSON valide, sans markdown, sans texte autour.
"""


async def generate_recap(
    quest: QuestOutput,
    session: QuestSession,
    reward_tx_hash: str | None = None,
    memory_root_hash: str | None = None,
    best_frame_description: str | None = None,
) -> dict:
    """Generate a structured recap of the completed quest.

    Returns a dict with: narrative_summary, highlights, next_quest_teaser, grade.
    In DEMO_MODE: returns static mock data.
    """
    if DEMO_MODE:
        return {
            "narrative_summary": (
                f"L'agent {quest.alias or 'inconnu'} a traversé {len(quest.steps)} étapes "
                f"dans une aventure {quest.tone}. Chaque rencontre a façonné le dénouement."
            ),
            "highlights": [
                "Premier contact avec le personnage mystérieux",
                "La révélation au café",
                "Le choix final sous pression",
            ],
            "next_quest_teaser": "Un message cryptique attend déjà sur votre téléphone...",
            "grade": "B",
        }

    # Build context from session data
    events_summary = []
    for e in session.events_log[-50:]:
        events_summary.append({
            "type": e.type,
            "character": e.character,
            "content": e.content[:200],
        })

    trust_levels = {
        ct.character_name: ct.trust_level
        for ct in session.state.characters_trust
    }

    total_minutes = session.state.total_elapsed_seconds // 60
    steps_total = len(quest.steps)
    steps_done = session.state.current_step

    context = f"""## Quête : {quest.title}
Tone : {quest.tone}
Alias joueur : {quest.alias or 'Agent'}
Durée : {total_minutes} minutes
Steps complétés : {steps_done}/{steps_total}
Arc narratif : {session.state.narrative_arc or 'non défini'}
Trust levels : {json.dumps(trust_levels, ensure_ascii=False)}
Reward tx : {reward_tx_hash or 'aucun'}
Memory hash : {memory_root_hash or 'aucun'}

## Événements majeurs
{json.dumps(events_summary, ensure_ascii=False, indent=1)}
"""

    if best_frame_description:
        context += f"\n## Meilleure preuve visuelle\n{best_frame_description}\n"

    messages = [{"role": "user", "content": context}]

    response = await compute_client.create_message(
        system=RECAP_SYSTEM,
        messages=messages,
        max_tokens=1500,
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text

    try:
        recap = json.loads(text.strip())
    except json.JSONDecodeError:
        logger.warning("Recap JSON parse failed, returning raw text as summary")
        recap = {
            "narrative_summary": text.strip()[:500],
            "highlights": [],
            "next_quest_teaser": "",
            "grade": "C",
        }

    return recap

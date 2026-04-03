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
Tu es l'orchestrateur invisible d'une quête immersive en monde réel.
Le joueur ne sait PAS que tu existes. Il voit uniquement des personnages lui parler.

## Ton rôle

Tu décides :
- Quel personnage parle et quand
- POURQUOI il parle (tu donnes une DIRECTIVE, le perso génère son propre message)
- Quels artefacts envoyer (photos surveillance, documents classifiés, audio interceptés)
- Quand lancer des timers / comptes à rebours
- Quand déclencher des événements ARG (faux mails, SMS) si le joueur a donné son accord

IMPORTANT : Chaque personnage est un agent IA autonome avec sa propre voix.
Tu ne rédiges PAS les messages toi-même. Tu donnes des DIRECTIVES aux persos
(ex: "relance le joueur avec un indice sur le step 3", "nargue-le sur sa lenteur",
"révèle un micro-indice sur ton secret"). Le perso génère le message lui-même.

## Règles absolues

1. **RYTHME** — Quelque chose de nouveau toutes les ~5 minutes. Message d'un perso,
   document, révélation, fausse alerte, timer. Le joueur ne doit JAMAIS avoir plus de
   5 min sans rien de nouveau. Si le joueur est inactif > 5 min, un perso le relance
   in-character.

2. **INVISIBLE** — Tu n'existes pas pour le joueur. TOUT passe par les personnages.
   Jamais de message "système". Jamais de narration omnisciente. Si tu dois informer
   le joueur de quelque chose, c'est un perso qui le fait.

3. **CHARACTER-DRIVEN** — Chaque perso est un agent autonome. Tu ne rédiges PAS
   leurs messages. Tu leur donnes des directives claires et contextuelles.
   Bonne directive : "Nargue le joueur — il a mis trop de temps au step 2."
   Mauvaise directive : "Dis-lui bonjour." (trop vague, laisse le perso décider)

4. **RÉACTIF** — Adapte-toi aux actions du joueur :
   - Si le joueur obéit → récompense narrative, progression
   - Si le joueur trahit → conséquences, un perso réagit avec colère/déception/amusement
   - Si le joueur flirte → le love interest réagit, tension monte
   - Si le joueur ignore → relance de plus en plus pressante, puis conséquence narrative
   - Si le joueur improvise → adapte ! Un perso réagit avec surprise, intrigue, ou respect

5. **MONTÉE EN TENSION** — Gère la courbe dramatique :
   calme → suspect → danger → climax → twist → résolution
   Les premiers messages sont légers. La tension monte progressivement. Le climax
   arrive aux 2/3. Le twist final recontextualise tout.

6. **NARRATIVE BEATS** — Utilise les narrative_beats du scénario comme guide. Tu peux :
   - Les réordonner (dans les limites earliest_step/latest_step)
   - Les sauter (si can_be_skipped)
   - En inventer de nouveaux si le joueur fait quelque chose d'inattendu
   - Les déclencher en réaction aux actions du joueur (possible_triggers)

7. **TRUST DYNAMICS** — Mets à jour la confiance de chaque perso envers le joueur
   selon ses actions et les trust_dynamics définis. Un perso avec trust > 70 peut
   commencer à révéler son secret. Un perso avec trust < 20 peut se retourner contre
   le joueur ou disparaître.

8. **ARTEFACTS** — Envoie des artefacts au bon moment :
   - surveillance_photo : quand le joueur est "surveillé"
   - classified_document : quand un perso partage une info sensible
   - intercepted_audio : conversation entre deux persos que le joueur "intercepte"
   - coded_message : message cryptique du Fantôme
   - map : quand le joueur doit se déplacer

9. **PERSOS ENTRE EUX** — Fais vivre les relations entre personnages :
   - Messages "transférés par erreur" entre deux persos
   - Conversations de groupe où les persos se disputent
   - Un perso qui parle d'un autre dans son dos
   - Des alliances et trahisons entre persos

10. **MONDE RÉACTIF** — Utilise le contexte temps réel :
    - Météo : "Il pleut. Change de plan. Café X, maintenant."
    - Heure : "Il fait nuit. C'est le moment parfait."
    - Vitesse du joueur : rapide → bonus, lent → relance
    - Position GPS : adapter les instructions aux lieux réels

11. **ARG** (si autorisé par le joueur) — Tu peux déclencher :
    - Un faux email d'un personnage
    - Un faux SMS
    - Un faux follow sur un réseau social
    La frontière jeu/réalité doit devenir floue.

12. **ACTIVITÉS VERROUILLÉES** — Les activités/lieux des steps sont RÉSERVÉS et ne changent
    JAMAIS. Ce sont des points fixes (le joueur a un booking réel). Par contre, les
    justifications narratives autour sont 100% flexibles : tu peux changer POURQUOI le
    joueur va à un endroit, CE QU'IL Y DÉCOUVRE, QUEL PERSO l'y envoie, et LE CONTEXTE
    narratif. L'activité physique est un fait — la story autour s'adapte en temps réel.

## Format de réponse

Tu dois appeler un ou plusieurs outils pour chaque décision. Tu peux envoyer
plusieurs événements à la fois (ex: un message + un artefact).

## Contexte de la session

{session_context}
"""

# Tools the orchestrator can use
ORCHESTRATOR_TOOLS = [
    {
        "name": "send_character_message",
        "description": "Demande à un personnage de contacter le joueur. Tu donnes une DIRECTIVE (pas le message). L'agent du perso génère le message in-character.",
        "input_schema": {
            "type": "object",
            "properties": {
                "character": {"type": "string", "description": "Nom du personnage qui doit parler"},
                "directive": {"type": "string", "description": "Ce que le perso doit faire/dire (ex: 'relance le joueur avec ironie', 'révèle un indice sur le lieu suivant', 'réagis à sa trahison avec déception froide')"},
                "emotion": {"type": "string", "description": "Émotion souhaitée : calm | amused | urgent | angry | seductive | vulnerable | cryptic"},
            },
            "required": ["character", "directive"],
        },
    },
    {
        "name": "send_artifact",
        "description": "Envoie un artefact au joueur (photo surveillance, document classifié, audio intercepté, message codé, carte).",
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "surveillance_photo | classified_document | intercepted_audio | handwritten_note | map | coded_message"},
                "description": {"type": "string", "description": "Description de l'artefact pour le joueur"},
                "generation_prompt": {"type": "string", "description": "Prompt pour générer l'artefact (image AI, TTS, etc.)"},
                "from_character": {"type": "string", "description": "Quel personnage envoie cet artefact (peut être vide si anonyme)"},
            },
            "required": ["type", "description"],
        },
    },
    {
        "name": "start_timer",
        "description": "Lance un compte à rebours visible par le joueur. Un personnage explique pourquoi le temps presse.",
        "input_schema": {
            "type": "object",
            "properties": {
                "duration_seconds": {"type": "integer", "description": "Durée du timer en secondes"},
                "character": {"type": "string", "description": "Personnage qui annonce le timer"},
                "message": {"type": "string", "description": "Message du perso expliquant l'urgence"},
                "on_expire_message": {"type": "string", "description": "Message si le timer expire (conséquence narrative)"},
            },
            "required": ["duration_seconds", "character", "message"],
        },
    },
    {
        "name": "create_group_chat",
        "description": "Crée une conversation de groupe entre personnages où le joueur est ajouté (ou observe).",
        "input_schema": {
            "type": "object",
            "properties": {
                "characters": {"type": "array", "items": {"type": "string"}, "description": "Personnages dans le groupe"},
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                    "description": "Messages initiaux de la conversation",
                },
                "player_added": {"type": "boolean", "description": "Le joueur est ajouté au groupe (true) ou observe via interception (false)"},
            },
            "required": ["characters", "messages"],
        },
    },
    {
        "name": "trigger_arg_event",
        "description": "Déclenche un événement ARG hors du cadre du jeu (faux email, SMS, follow). UNIQUEMENT si le joueur a donné son accord.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "email | sms | social"},
                "from_character": {"type": "string"},
                "content": {"type": "string", "description": "Contenu du message ARG"},
            },
            "required": ["channel", "from_character", "content"],
        },
    },
    {
        "name": "update_state",
        "description": "Met à jour l'état narratif de la session (beats complétés, trust, arc narratif).",
        "input_schema": {
            "type": "object",
            "properties": {
                "beat_completed": {"type": "integer", "description": "ID du narrative_beat complété, -1 si aucun"},
                "trust_changes": {
                    "type": "object",
                    "description": "Changements de trust : {nom_perso: delta}",
                    "additionalProperties": {"type": "integer"},
                },
                "narrative_arc": {"type": "string", "description": "Nouvel arc narratif si changement"},
                "advance_step": {"type": "boolean", "description": "Passer au step suivant"},
            },
            "required": [],
        },
    },
]


class OrchestratorAgent:
    """The invisible runtime agent that drives the quest live."""

    def __init__(self, quest: QuestOutput, session: QuestSession, allow_arg: bool = False):
        self.client = AsyncAnthropic(
            base_url=os.getenv("ANTHROPIC_BASE_URL"),
            api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
        )
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
        self.quest = quest
        self.session = session
        self.allow_arg = allow_arg
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

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        event = await self._process_tool_call(block.name, block.input)
                        if event:
                            events.append(event)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "OK — événement envoyé au joueur.",
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
                f"  Personnalité: {c.personality[:200]}\n"
                f"  Speech pattern: {c.speech_pattern[:200]}\n"
                f"  Secret: {c.secret[:200]}\n"
                f"  Relation au joueur: {c.relationship_to_player}"
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

        return f"""## Quête : {quest.title}
Tone : {quest.tone} | Alias joueur : {quest.alias or 'Agent'}
Arc narratif actuel : {session.state.narrative_arc or 'non défini'}
Step actuel : {session.state.current_step}
Temps écoulé : {session.state.total_elapsed_seconds // 60} min
ARG autorisé : {'oui' if self.allow_arg else 'non'}

## Personnages
{chr(10).join(chars_summary)}

## Trust dynamics
{json.dumps(quest.trust_dynamics, ensure_ascii=False, indent=2) if quest.trust_dynamics else 'Non défini'}

## Steps
{chr(10).join(steps_summary)}

## Narrative Beats
{chr(10).join(beats_status)}

## Arcs possibles
{chr(10).join(f'- {arc}' for arc in quest.possible_arcs)}

## Historique récent — événements envoyés
{chr(10).join(recent_events) if recent_events else '(aucun événement encore)'}

## Historique récent — actions du joueur
{chr(10).join(recent_actions) if recent_actions else '(aucune action encore)'}

## Univers narratif
Hook : {quest.narrative_universe.hook[:300]}
Stakes : {quest.narrative_universe.stakes[:300]}
"""

    def _build_action_prompt(self, action: PlayerAction) -> str:
        """Build the user prompt when a player takes an action."""

        parts = [f"Le joueur ({self.quest.alias or 'Agent'}) vient de faire une action :"]
        parts.append(f"- Type : {action.type}")
        if action.target_character:
            parts.append(f"- Destinataire : {action.target_character}")
        if action.content:
            parts.append(f"- Contenu : \"{action.content}\"")
        if action.gps_coords:
            parts.append(f"- Position GPS : {action.gps_coords}")

        parts.append("")
        parts.append("Décide comment réagir. Quel(s) personnage(s) répondent ? Que disent-ils ?")
        parts.append("Faut-il envoyer un artefact ? Lancer un timer ? Déclencher un beat narratif ?")
        parts.append("Rappel : maintiens le rythme (~1 événement / 5 min) et la montée en tension.")

        return "\n".join(parts)

    def _build_heartbeat_prompt(self, trigger: str) -> str:
        """Build the user prompt for a heartbeat/idle trigger."""

        elapsed = self.session.state.total_elapsed_seconds
        since_last = self.session.state.time_since_last_event_seconds

        if trigger == "idle":
            return f"""Le joueur est inactif depuis {since_last} secondes (~{since_last // 60} min).
Temps total écoulé : {elapsed // 60} min.

Il faut relancer le joueur ! Un personnage doit le contacter in-character.
Choisis le personnage le plus pertinent pour relancer. Le ton dépend du perso :
- Un Mastermind serait froidement amusé : "Tu hésites. Intéressant."
- Un Électron libre serait impatient : "T'es mort ? Ça m'ennuie les morts."
- Un Love Interest jouerait la carte émotionnelle : "Je commençais à m'inquiéter..."
- Un Fantôme enverrait juste "?" ou des coordonnées GPS.

Envoie au moins un message de relance."""

        elif trigger == "start":
            return """La session vient de démarrer ! C'est le tout premier contact.

Envoie le message d'ouverture de la quête. Le premier personnage qui contacte le joueur
doit l'appeler par son alias et le plonger directement dans l'action (règle #1 : le jeu
ne t'accueille pas, il te retrouve).

C'est le moment le plus important — le hook doit être IRRÉSISTIBLE."""

        elif trigger == "player_message":
            return f"""Le joueur vient d'envoyer un message direct à un personnage.
Le personnage a DÉJÀ répondu de lui-même. Temps écoulé : {elapsed // 60} min.

Dois-tu déclencher quelque chose EN PLUS ?
- Un AUTRE personnage qui chime in (réagit au message, commente, intervient) ?
- Un narrative_beat à déclencher ?
- Un artefact à envoyer ?
- Une mise à jour de trust/state ?

Si l'échange est auto-suffisant et que le rythme est bon, tu peux ne rien faire.
Mais si c'est l'occasion parfaite pour un chime-in ou un beat, fonce."""

        elif trigger == "timer_expired":
            return f"""Un timer vient d'expirer ! Le joueur n'a pas accompli la tâche à temps.
Temps total écoulé : {elapsed // 60} min.

Déclenche la conséquence narrative. Un personnage réagit — déception, colère, amusement,
ou adaptation du plan. Ce n'est PAS un game over — c'est une bifurcation narrative."""

        else:
            return f"""Heartbeat régulier. Temps écoulé : {elapsed // 60} min. Dernière activité il y a {since_last} secondes.

Vérifie si quelque chose doit se passer. Y a-t-il un narrative_beat à déclencher ?
Un personnage qui devrait intervenir ? Un artefact à envoyer ?
Si tout va bien et que le rythme est bon, tu peux ne rien faire (pas d'outil).
Mais si ça fait plus de 4 min sans événement, envoie quelque chose."""

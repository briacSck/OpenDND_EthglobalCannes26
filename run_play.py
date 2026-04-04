"""Interactive CLI to test the quest orchestrator live.

Commands:
  msg <character> <message>   — Send a message to a character
  see <description>           — Simulate what Ray-Ban Meta glasses see (camera/vision)
  move <lieu>                 — Simulate GPS move (e.g. "move Carlton", "move Suquet")
  photo <description>         — Simulate sending a photo from the app
  wait                        — Trigger a heartbeat (idle — characters may ping you)
  status                      — Quest state overview
  chars                       — Character details + trust
  steps                       — Step progression
  history                     — Recent events timeline
  help                        — This help
  quit                        — Exit
"""

import asyncio
import json
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.stderr.reconfigure(encoding="utf-8")

from agents.quest_generation.models import QuestOutput
from agents.quest_runtime.orchestrator import OrchestratorAgent
from agents.quest_runtime.models import (
    QuestSession, SessionState, PlayerAction, CharacterTrust,
)


# Known places in Cannes with GPS coords
CANNES_PLACES = {
    "suquet": ("Le Suquet (vieux Cannes médiéval)", 43.5510, 7.0130),
    "castre": ("Musée de la Castre, Le Suquet", 43.5513, 7.0128),
    "tour": ("Tour du Suquet", 43.5513, 7.0128),
    "croisette": ("Boulevard de la Croisette", 43.5519, 7.0200),
    "carlton": ("Hôtel Carlton, La Croisette", 43.5519, 7.0231),
    "martinez": ("Hôtel Martinez, La Croisette", 43.5515, 7.0265),
    "majestic": ("Hôtel Majestic, La Croisette", 43.5522, 7.0188),
    "palais": ("Palais des Festivals", 43.5516, 7.0174),
    "forville": ("Marché Forville", 43.5520, 7.0143),
    "meynadier": ("Rue Meynadier", 43.5525, 7.0148),
    "port": ("Vieux Port de Cannes", 43.5505, 7.0155),
    "canto": ("Port Canto (marina yachts)", 43.5480, 7.0310),
    "marguerite": ("Île Sainte-Marguerite", 43.5270, 7.0460),
    "ile": ("Île Sainte-Marguerite", 43.5270, 7.0460),
    "fort": ("Fort Royal, Île Sainte-Marguerite", 43.5267, 7.0470),
    "lerins": ("Île Saint-Honorat (Abbaye de Lérins)", 43.5080, 7.0480),
    "rothschild": ("Villa Rothschild", 43.5540, 7.0195),
    "californie": ("Quartier de la Californie", 43.5480, 7.0350),
    "gare": ("Gare SNCF Cannes", 43.5535, 7.0170),
    "antibes": ("Rue d'Antibes", 43.5530, 7.0180),
    "esperance": ("Église Notre-Dame d'Espérance", 43.5512, 7.0125),
}


def resolve_place(query: str) -> tuple[str, float, float] | None:
    """Fuzzy-match a place name. Returns (name, lat, lon) or None."""
    q = query.lower().strip()
    # Exact match
    if q in CANNES_PLACES:
        return CANNES_PLACES[q]
    # Partial match
    matches = [(k, v) for k, v in CANNES_PLACES.items() if q in k or q in v[0].lower()]
    if len(matches) == 1:
        return matches[0][1]
    if len(matches) > 1:
        # Try stricter: starts with
        strict = [(k, v) for k, v in matches if k.startswith(q)]
        if len(strict) == 1:
            return strict[0][1]
        return matches[0][1]  # Best guess
    return None


def load_quest(path: str = "quest_highstakes.json") -> QuestOutput:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return QuestOutput(**data)


def create_session(quest: QuestOutput) -> QuestSession:
    """Create a fresh session with trust initialized for all characters."""
    trusts = [
        CharacterTrust(character_name=c.name, trust_level=50)
        for c in quest.characters
    ]
    return QuestSession(
        quest_id=quest.quest_id,
        player_alias=quest.alias or "Agent",
        state=SessionState(
            current_step=0,
            characters_trust=trusts,
        ),
    )


def print_colored(text: str, color: str = "white"):
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "gray": "\033[90m",
        "bold": "\033[1m",
        "reset": "\033[0m",
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


def show_status(quest: QuestOutput, session: QuestSession):
    state = session.state
    current = state.current_step
    total_steps = len(quest.steps)

    print_colored(f"\n{'='*60}", "cyan")
    print_colored(f"  QUEST: {quest.title}", "bold")
    print_colored(f"  Alias: {quest.alias} | Tone: {quest.tone}", "cyan")
    print_colored(f"{'='*60}", "cyan")

    # Progress
    print_colored(f"\n  Step: {current}/{total_steps-1}", "yellow")
    if current < total_steps:
        step = quest.steps[current]
        print_colored(f"  Current: {step.title}", "yellow")
        print_colored(f"  Activity: {step.activity.name} @ {step.activity.address}", "white")
        print_colored(f"  Instruction: {step.instruction[:200]}", "gray")

    # Trust levels
    print_colored(f"\n  Characters:", "magenta")
    for ct in state.characters_trust:
        bar = "█" * (ct.trust_level // 5) + "░" * (20 - ct.trust_level // 5)
        char = next((c for c in quest.characters if c.name == ct.character_name), None)
        archetype = f" ({char.archetype})" if char and char.archetype else ""
        print_colored(f"    {ct.character_name}{archetype}: [{bar}] {ct.trust_level}/100", "white")

    # Beats
    completed_beats = state.beats_completed
    print_colored(f"\n  Narrative beats: {len(completed_beats)}/{len(quest.narrative_beats)} completed", "green")

    # Tensions
    if quest.narrative_tensions:
        print_colored(f"\n  Tensions:", "red")
        for t in quest.narrative_tensions:
            print_colored(f"    - {t}", "white")

    print_colored(f"\n  Events sent: {len(session.events_log)} | Player actions: {len(session.actions_log)}", "gray")
    print()


def show_characters(quest: QuestOutput, session: QuestSession):
    print_colored(f"\n{'='*60}", "magenta")
    print_colored(f"  CHARACTERS", "bold")
    print_colored(f"{'='*60}", "magenta")
    for c in quest.characters:
        trust = 50
        for ct in session.state.characters_trust:
            if ct.character_name == c.name:
                trust = ct.trust_level
                break
        print_colored(f"\n  {c.name} ({c.type} — {c.archetype})", "bold")
        print_colored(f"    Personality: {c.personality[:150]}", "white")
        print_colored(f"    Speech: {c.speech_pattern[:150]}", "gray")
        print_colored(f"    Relation: {c.relationship_to_player[:150]}", "cyan")
        print_colored(f"    Secret: {c.secret[:150]}", "red")
        print_colored(f"    Trust: {trust}/100", "yellow")
    print()


def show_steps(quest: QuestOutput, session: QuestSession):
    current = session.state.current_step
    print_colored(f"\n{'='*60}", "yellow")
    print_colored(f"  STEPS", "bold")
    print_colored(f"{'='*60}", "yellow")
    for s in quest.steps:
        marker = "→" if s.step_id == current else ("✓" if s.step_id < current else " ")
        color = "green" if s.step_id < current else ("yellow" if s.step_id == current else "gray")
        print_colored(f"\n  {marker} Step {s.step_id}: {s.title}", color)
        print_colored(f"    {s.activity.name} — {s.activity.address}", "white" if s.step_id <= current else "gray")
        if s.step_id == current:
            print_colored(f"    Instruction: {s.instruction[:200]}", "cyan")
            if s.verification.method:
                print_colored(f"    Verification: {s.verification.method} — {s.verification.target}", "yellow")
                if s.verification.success_reaction:
                    print_colored(f"      Success: {s.verification.success_reaction[:100]}", "green")
                if s.verification.failure_fallback:
                    print_colored(f"      Failure: {s.verification.failure_fallback[:100]}", "red")
    print()


def show_history(session: QuestSession):
    print_colored(f"\n{'='*60}", "gray")
    print_colored(f"  RECENT HISTORY (last 15)", "bold")
    print_colored(f"{'='*60}", "gray")

    # Interleave events and actions by timestamp
    items = []
    for e in session.events_log[-15:]:
        items.append(("event", e.timestamp, e))
    for a in session.actions_log[-15:]:
        items.append(("action", a.timestamp, a))
    items.sort(key=lambda x: x[1])

    for kind, ts, item in items[-15:]:
        time_short = ts[11:19] if len(ts) > 19 else ts
        if kind == "event":
            if item.type == "character_message":
                print_colored(f"  [{time_short}] 💬 {item.character}: {item.content[:200]}", "cyan")
            elif item.type == "artifact":
                print_colored(f"  [{time_short}] 📎 Artifact ({item.artifact.type if item.artifact else '?'}): {item.content[:150]}", "magenta")
            elif item.type == "timer":
                print_colored(f"  [{time_short}] ⏱ Timer {item.timer_seconds}s — {item.content[:150]}", "red")
            else:
                print_colored(f"  [{time_short}] 📌 {item.type}: {item.content[:150]}", "yellow")
        else:
            print_colored(f"  [{time_short}] 🎮 Player ({item.type}): {item.content[:150]}", "green")
    print()


def print_events(events):
    """Pretty-print orchestrator events."""
    for e in events:
        if e.type == "character_message":
            print_colored(f"\n  💬 {e.character}:", "cyan")
            print_colored(f"  {e.content}", "white")
        elif e.type == "artifact":
            art_type = e.artifact.type if e.artifact else "?"
            print_colored(f"\n  📎 [{art_type}] from {e.character or 'anonymous'}:", "magenta")
            print_colored(f"  {e.content}", "white")
        elif e.type == "timer":
            print_colored(f"\n  ⏱ Timer ({e.timer_seconds}s) — {e.character}:", "red")
            print_colored(f"  {e.content}", "white")
        elif e.type == "group_chat":
            print_colored(f"\n  👥 Group chat:", "yellow")
            print_colored(f"  {e.content}", "white")
        elif e.type == "forwarded_message":
            print_colored(f"\n  📨 Intercepted message:", "red")
            print_colored(f"  {e.content}", "white")
        elif e.type == "arg_event":
            print_colored(f"\n  🌐 ARG [{e.arg_channel}] from {e.character}:", "red")
            print_colored(f"  {e.content}", "white")
    print()


HELP = """
Commands:
  msg <character> <message>   — Talk to a character
  see <description>           — What your Ray-Ban Meta glasses see
  photo <description>         — Send a photo from the app
  move <lieu>                 — Move to a place (e.g. "move Carlton", "move Suquet")
  places                      — List known places
  wait                        — Idle heartbeat (triggers character pings)
  status                      — Quest state overview
  chars                       — Character details + trust
  steps                       — Step progression
  history                     — Recent events timeline
  help                        — This help
  quit                        — Exit

The orchestrator's internal reasoning is shown in [gray] so you can
see how it decides which character speaks, when, and why.
"""


def debug_print(msg_type: str, data):
    """Show orchestrator internal reasoning and tool calls."""
    if msg_type == "reasoning":
        print_colored(f"\n  ┌─ ORCHESTRATOR REASONING ─────────────────────────", "gray")
        for line in data.strip().split("\n"):
            print_colored(f"  │ {line}", "gray")
        print_colored(f"  └──────────────────────────────────────────────────", "gray")
    elif msg_type == "tool_call":
        name = data["name"]
        inp = data["input"]
        if name == "send_character_message":
            print_colored(f"  ⚙ Orchestrator → {inp.get('character','?')}: \"{inp.get('directive','')}\" (emotion: {inp.get('emotion','?')})", "yellow")
        elif name == "send_artifact":
            print_colored(f"  ⚙ Orchestrator sends artifact [{inp.get('type','')}]: {inp.get('description','')[:100]}", "yellow")
        elif name == "start_timer":
            print_colored(f"  ⚙ Orchestrator starts timer: {inp.get('duration_seconds',0)}s via {inp.get('character','?')}", "yellow")
        elif name == "update_state":
            parts = []
            if inp.get("beat_completed", -1) >= 0:
                parts.append(f"beat {inp['beat_completed']} completed")
            if inp.get("trust_changes"):
                parts.append(f"trust: {inp['trust_changes']}")
            if inp.get("advance_step"):
                parts.append("→ next step")
            if inp.get("narrative_arc"):
                parts.append(f"arc: {inp['narrative_arc']}")
            print_colored(f"  ⚙ State update: {', '.join(parts) or 'no change'}", "yellow")
        else:
            print_colored(f"  ⚙ {name}: {json.dumps(inp, ensure_ascii=False)[:200]}", "yellow")


async def main():
    # Load quest
    quest_path = "quest_highstakes.json"
    if not os.path.exists(quest_path):
        print(f"Quest file not found: {quest_path}")
        print("Run the pipeline first: python run_generate.py")
        return

    print_colored("Loading quest...", "gray")
    quest = load_quest(quest_path)
    session = create_session(quest)
    orchestrator = OrchestratorAgent(quest, session, allow_arg=False, debug_callback=debug_print)

    print_colored(f"\n{'='*60}", "bold")
    print_colored(f"  🎮 QUEST LIVE: {quest.title}", "bold")
    print_colored(f"  You are: {quest.alias}", "cyan")
    print_colored(f"  {len(quest.steps)} steps | {len(quest.characters)} characters", "white")
    print_colored(f"{'='*60}", "bold")

    # Kick off with initial orchestrator reaction
    print_colored("\n  Starting quest... The orchestrator is setting the scene.\n", "yellow")
    try:
        events = await orchestrator.react("quest_start")
        print_events(events)
    except Exception as e:
        print_colored(f"  Error on start: {e}", "red")

    char_names = [c.name for c in quest.characters]
    char_names_lower = {c.name.lower(): c.name for c in quest.characters}

    while True:
        try:
            raw = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not raw:
            continue

        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "quit" or cmd == "exit":
            print("Bye!")
            break

        elif cmd == "help":
            print(HELP)

        elif cmd == "status":
            show_status(quest, session)

        elif cmd == "chars":
            show_characters(quest, session)

        elif cmd == "steps":
            show_steps(quest, session)

        elif cmd == "history":
            show_history(session)

        elif cmd == "msg":
            # Parse: msg <character_name> <message>
            msg_parts = arg.split(maxsplit=1)
            if len(msg_parts) < 2:
                print_colored("  Usage: msg <character> <message>", "red")
                print_colored(f"  Characters: {', '.join(char_names)}", "gray")
                continue

            char_query = msg_parts[0].lower()
            message = msg_parts[1]

            # Fuzzy match character name
            matched = char_names_lower.get(char_query)
            if not matched:
                # Try partial match
                matches = [name for key, name in char_names_lower.items() if char_query in key]
                if len(matches) == 1:
                    matched = matches[0]
                elif len(matches) > 1:
                    # Try first name match
                    first_name_matches = [name for key, name in char_names_lower.items() if key.startswith(char_query)]
                    if len(first_name_matches) == 1:
                        matched = first_name_matches[0]
                    else:
                        print_colored(f"  Ambiguous: {', '.join(matches)}", "red")
                        continue
                else:
                    print_colored(f"  Unknown character: {char_query}", "red")
                    print_colored(f"  Characters: {', '.join(char_names)}", "gray")
                    continue

            print_colored(f"  → Sending to {matched}...", "gray")
            try:
                # Character responds directly — NO orchestrator intervention
                char_agent = orchestrator.get_character_agent(matched)
                if char_agent:
                    response = await char_agent.respond(message)
                    print_events([response])

                # Log the action for history tracking
                action = PlayerAction(
                    type="message",
                    content=message,
                    target_character=matched,
                )
                session.actions_log.append(action)
            except Exception as e:
                print_colored(f"  Error: {e}", "red")

        elif cmd == "see":
            if not arg:
                print_colored("  Usage: see <what the Ray-Ban glasses see>", "red")
                continue
            print_colored(f"  👓 Ray-Ban sees: {arg}", "gray")
            action = PlayerAction(
                type="custom",
                content=f"[Ray-Ban Meta vision] {arg}",
            )
            try:
                events = await orchestrator.react("rayban_vision", action)
                print_events(events)
            except Exception as e:
                print_colored(f"  Error: {e}", "red")

        elif cmd == "photo":
            if not arg:
                print_colored("  Usage: photo <description of photo sent>", "red")
                continue
            print_colored(f"  📷 Photo sent: {arg}", "gray")
            action = PlayerAction(
                type="custom",
                content=f"[Photo envoyée par le joueur] {arg}",
            )
            try:
                events = await orchestrator.react("player_photo", action)
                print_events(events)
            except Exception as e:
                print_colored(f"  Error: {e}", "red")

        elif cmd == "move":
            if not arg:
                print_colored("  Usage: move <lieu> (e.g. move Carlton, move Suquet)", "red")
                print_colored("  Type 'places' to see known locations", "gray")
                continue
            place = resolve_place(arg)
            if not place:
                print_colored(f"  Unknown place: {arg}", "red")
                print_colored("  Type 'places' to see known locations", "gray")
                continue
            name, lat, lon = place
            print_colored(f"  📍 Moved to: {name} ({lat}, {lon})", "green")
            action = PlayerAction(
                type="move",
                content=f"Le joueur se déplace vers {name} (GPS: {lat}, {lon})",
                gps_coords=[lat, lon],
            )
            try:
                events = await orchestrator.react("player_move", action)
                print_events(events)
            except Exception as e:
                print_colored(f"  Error: {e}", "red")

        elif cmd == "places":
            print_colored(f"\n  Known places in Cannes:", "bold")
            for key, (name, lat, lon) in sorted(CANNES_PLACES.items()):
                print_colored(f"    {key:15s} — {name} ({lat}, {lon})", "white")
            print()

        elif cmd == "wait":
            print_colored("  ⏳ Waiting... (heartbeat)", "gray")
            session.state.time_since_last_event_seconds += 300  # Simulate 5min idle
            session.state.total_elapsed_seconds += 300
            try:
                events = await orchestrator.react("heartbeat")
                print_events(events)
            except Exception as e:
                print_colored(f"  Error: {e}", "red")

        else:
            print_colored(f"  Unknown command: {cmd}. Type 'help' for commands.", "red")


if __name__ == "__main__":
    asyncio.run(main())

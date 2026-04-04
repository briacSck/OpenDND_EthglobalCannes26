"""Quest Generation Pipeline — orchestrates Storyteller ↔ Curator → Judge → Characters."""

from __future__ import annotations

import builtins
import json
import os
import uuid

from agents.city_research.models import CityContext
from agents.quest_generation.models import (
    QuestRequest, QuestOutput, NarrativeUniverse, GenerationMeta,
    PreQuestBundle, EmailBundle, VoicemailBundle, PdfBundle, PlaylistBundle,
    CharacterSystem, BudgetConfirmed,
    Step, ActivityRef, Tension, CharacterInteraction, RayBanVersion,
    CameraMode, ContextualMusic, Verification, Resolution, Prize, NftMetadata,
    NarrativeBeat, Character, MemoryState,
)
from agents.quest_generation.storyteller import StorytellerAgent
from agents.quest_generation.judge import JudgeAgent
from agents.quest_generation.characters import CharacterInitializer

MAX_JUDGE_ITERATIONS = 3


_print = builtins.print


def log(msg: str):
    _print(msg, flush=True)


CHECKPOINT_DIR = "checkpoints"


def _save_checkpoint(name: str, data):
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    path = os.path.join(CHECKPOINT_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        if hasattr(data, "model_dump"):
            json.dump([d.model_dump() for d in data] if isinstance(data, list) else data.model_dump(), f, ensure_ascii=False, indent=2)
        else:
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


async def generate_quest(request: QuestRequest, city_context: CityContext) -> QuestOutput:
    """Full pipeline with checkpoints: Storyteller ↔ Curator → Judge → Characters."""

    log("=" * 60)
    log("QUEST GENERATION PIPELINE")
    log("=" * 60)

    # --- Phase 1: Storyteller ↔ Curator ---
    # Storyteller now manages its own granular checkpoints (concept, step_1..N, meta)
    log("\n[Phase 1] Storyteller <-> Curator dialogue...")
    storyteller = StorytellerAgent(request, city_context)
    quest_raw = await storyteller.generate()
    curator_iterations = storyteller.curator_iterations
    _save_checkpoint("quest_raw", quest_raw)

    log(f"\n  Quest draft received: \"{quest_raw.get('title', '???')}\"")
    log(f"  Curator iterations: {curator_iterations}")

    # --- Phase 2: Judge ---
    judge_cache = _load_checkpoint("judge_result")
    if judge_cache is None:
        log("\n[Phase 2] Judge evaluation...")
        judge = JudgeAgent()
        judge_iterations = 0
        judge_score = 0

        request_context = {
            "tone": request.tone,
            "skill": request.skill,
            "budget": request.budget,
            "duration": request.duration,
            "players": request.players,
        }

        for i in range(MAX_JUDGE_ITERATIONS):
            judge_iterations = i + 1
            log(f"\n  Judge iteration {judge_iterations}...")

            result = await judge.evaluate(quest_raw, request_context)
            judge_score = result.score

            log(f"  Score: {result.score}/100 — {'VALIDATED' if result.validated else 'REJECTED'}")
            log(f"  Breakdown: {result.breakdown}")

            if result.validated:
                break

            if i < MAX_JUDGE_ITERATIONS - 1:
                log(f"  Feedback: {len(result.feedback)} items → regenerating from scratch with feedback")
                for fb in result.feedback:
                    log(f"    [{fb['agent']}] {fb['issue']}")

                # Clear all generation checkpoints to force full regeneration
                import glob as glob_mod
                for cp_file in glob_mod.glob(os.path.join(CHECKPOINT_DIR, "*.json")):
                    fname = os.path.basename(cp_file)
                    if fname not in ("judge_result.json",):
                        os.remove(cp_file)
                        log(f"  [Checkpoint] Deleted {fname}")

                # Inject feedback into storyteller prompt and regenerate step by step
                feedback_text = "\n".join(
                    f"- [{fb['agent']}] {fb['issue']} → {fb['instruction']}"
                    for fb in result.feedback
                )
                storyteller.judge_feedback = feedback_text
                quest_raw = await storyteller.generate()
                _save_checkpoint("quest_raw", quest_raw)
                log(f"  Regenerated quest: \"{quest_raw.get('title', '???')}\"")
            else:
                log("  Max iterations reached — forcing validation.")

        _save_checkpoint("judge_result", {"score": judge_score, "iterations": judge_iterations})
    else:
        log("\n[Phase 2] Skipped — loaded from checkpoint")
        judge_score = judge_cache["score"]
        judge_iterations = judge_cache["iterations"]

    # --- Phase 3: Character enrichment (per-character checkpoints) ---
    log("\n[Phase 3] Character initialization...")
    quest_context = quest_raw.get("narrative_universe", {}).get("context", "")
    char_init = CharacterInitializer(tone=request.tone, quest_context=quest_context)
    raw_characters = quest_raw.get("characters", [])
    characters = []
    for idx, raw_char in enumerate(raw_characters):
        char_cache = _load_checkpoint(f"character_{idx}")
        if char_cache is not None:
            characters.append(Character(**char_cache))
            log(f"  Character {idx} ({raw_char.get('name', '?')}): loaded from checkpoint")
        else:
            enriched = await char_init.enrich_one(raw_char)
            characters.append(enriched)
            _save_checkpoint(f"character_{idx}", enriched)
            log(f"  Character {idx} ({enriched.name}): enriched & saved")
    log(f"  Total: {len(characters)} characters")

    # --- Phase 4: Assemble final QuestOutput ---
    log("\n[Phase 4] Assembling final output...")
    quest_output = _assemble_quest(quest_raw, request, characters, curator_iterations, judge_iterations, judge_score)

    log(f"\n{'=' * 60}")
    log(f"QUEST READY: \"{quest_output.title}\"")
    log(f"Score: {judge_score}/100 | Steps: {len(quest_output.steps)} | Characters: {len(quest_output.characters)}")
    log(f"{'=' * 60}")

    return quest_output


def _assemble_quest(
    raw: dict,
    request: QuestRequest,
    characters: list,
    curator_iterations: int,
    judge_iterations: int,
    judge_score: int,
) -> QuestOutput:
    """Convert raw Storyteller output + enriched characters into QuestOutput."""

    # Narrative universe
    nu_raw = raw.get("narrative_universe", {})
    narrative = NarrativeUniverse(
        hook=nu_raw.get("hook", ""),
        context=nu_raw.get("context", ""),
        protagonist=nu_raw.get("protagonist", ""),
        stakes=nu_raw.get("stakes", ""),
    )

    # Pre-quest bundle
    pq_raw = raw.get("pre_quest_bundle", {})
    pre_quest = PreQuestBundle(
        email=EmailBundle(**pq_raw.get("email", {})) if pq_raw.get("email") else EmailBundle(),
        voicemail=VoicemailBundle(**pq_raw.get("voicemail", {})) if pq_raw.get("voicemail") else VoicemailBundle(),
        pdf=PdfBundle(**pq_raw.get("pdf", {})) if pq_raw.get("pdf") else PdfBundle(),
        playlist=PlaylistBundle(**pq_raw.get("playlist", {})) if pq_raw.get("playlist") else PlaylistBundle(),
    )

    # Steps
    steps = []
    for s in raw.get("steps", []):
        act_raw = s.get("activity", {})
        tension_raw = s.get("tension", {})
        verif_raw = s.get("verification", {})

        char_ints = []
        for ci in s.get("character_interactions", []):
            if isinstance(ci, str):
                continue  # Skip malformed entries
            rb_raw = ci.get("rayban_version", {})
            cam_raw = rb_raw.get("camera_mode", {}) if rb_raw else {}
            mus_raw = rb_raw.get("contextual_music", {}) if rb_raw else {}

            char_ints.append(CharacterInteraction(
                character=ci.get("character", ""),
                trigger=ci.get("trigger", ""),
                phone_version=ci.get("phone_version", ""),
                rayban_version=RayBanVersion(
                    script=rb_raw.get("script", "") if rb_raw else "",
                    duration_seconds=rb_raw.get("duration_seconds", 20) if rb_raw else 20,
                    audio_type=rb_raw.get("audio_type", "narration") if rb_raw else "narration",
                    camera_mode=CameraMode(**cam_raw) if cam_raw else CameraMode(),
                    contextual_music=ContextualMusic(**mus_raw) if mus_raw else ContextualMusic(),
                ),
                awaits_response=ci.get("awaits_response", True),
            ))

        steps.append(Step(
            step_id=s.get("step_id", 0),
            is_collaborative=s.get("is_collaborative", False),
            is_skill_step=s.get("is_skill_step", False),
            title=s.get("title", ""),
            activity=ActivityRef(**act_raw) if act_raw else ActivityRef(name=""),
            narrative_intro=s.get("narrative_intro", ""),
            instruction=s.get("instruction", ""),
            tension=Tension(**tension_raw) if tension_raw else Tension(),
            character_interactions=char_ints,
            verification=Verification(**verif_raw) if verif_raw else Verification(),
            walking_minutes_from_previous=s.get("walking_minutes_from_previous", 0),
            player_action=s.get("player_action", ""),
            gps_trigger=s.get("gps_trigger", {}),
            camera_prompt=s.get("camera_prompt", ""),
            blockchain_event=s.get("blockchain_event"),
            unlock_message=s.get("unlock_message", ""),
            skill_xp=s.get("skill_xp", 0),
        ))

    # Budget
    total_cost = sum(s.activity.price_eur for s in steps)
    budget = BudgetConfirmed(
        total=request.budget,
        pre_quest=15,
        activities=total_cost,
        reward=min(request.budget * 0.3, 60),
        within_budget=total_cost + 15 + min(request.budget * 0.3, 60) <= request.budget,
    )

    # Resolution
    res_raw = raw.get("resolution", {})
    prize_raw = res_raw.get("prize", {})

    # Generation meta
    meta = GenerationMeta(
        scout_direction_chosen="A",
        storyteller_curator_iterations=curator_iterations,
        judge_iterations=judge_iterations,
        judge_final_score=judge_score,
    )

    # Narrative beats
    narrative_beats = []
    for nb in raw.get("narrative_beats", []):
        narrative_beats.append(NarrativeBeat(
            beat_id=nb.get("beat_id", 0),
            description=nb.get("description", ""),
            characters_involved=nb.get("characters_involved", []),
            earliest_step=nb.get("earliest_step", 0),
            latest_step=nb.get("latest_step", 99),
            tension_level=nb.get("tension_level", "medium"),
            can_be_skipped=nb.get("can_be_skipped", False),
            possible_triggers=nb.get("possible_triggers", []),
        ))

    return QuestOutput(
        quest_id=str(uuid.uuid4()),
        title=raw.get("title", "Unnamed Quest"),
        tone=request.tone,
        alias=raw.get("alias", ""),
        generation_meta=meta,
        pre_quest_bundle=pre_quest,
        narrative_universe=narrative,
        character_system=CharacterSystem(
            max_active=15,
            principals=[c.name for c in characters if c.type == "principal"],
        ),
        characters=characters,
        budget_confirmed=budget,
        steps=steps,
        narrative_beats=narrative_beats,
        narrative_tensions=raw.get("narrative_tensions", []),
        twist=raw.get("twist", {}),
        resolution_principles=raw.get("resolution_principles", []),
        trust_dynamics=raw.get("trust_dynamics", {}),
        resolution=Resolution(
            skill_gained=res_raw.get("skill_gained", request.skill),
            prize=Prize(
                xp_total=prize_raw.get("xp_total", 0),
                token_amount=prize_raw.get("token_amount", 0),
                nft_metadata=NftMetadata(
                    city=request.location,
                    date=request.datetime,
                    quest_title=raw.get("title", ""),
                ),
            ),
        ),
    )

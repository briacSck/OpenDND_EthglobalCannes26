"""Pydantic models for Quest Generation — v5 JSON output schema."""

from __future__ import annotations

import uuid
from pydantic import BaseModel, Field


# --- Quest Request (extended with tone + skill) ---

class QuestRequest(BaseModel):
    goal: str = Field(description="What the user wants: sport, culture, music, meeting people, etc.")
    vibe: str = Field(default="", description="Desired atmosphere: mystere, aventure, chill, epic, etc.")
    duration: str = Field(description="Quest duration: 5mn, 2h, 4h, etc.")
    budget: float = Field(description="Budget in euros")
    location: str = Field(description="City or neighborhood: Cannes, Paris 3eme, etc.")
    difficulty: str = Field(default="life-maxing", description="easy-peasy | life-maxing | god-mode")
    players: int = Field(default=1, description="Number of players")
    datetime: str = Field(description="When the quest starts: 2026-04-05 10:00")
    tone: str = Field(default="loufoque", description="loufoque | high_stakes")
    skill: str = Field(default="", description="Skill to develop: exploration urbaine, cuisine, etc.")
    player_email: str = Field(default="", description="Player email for booking forms (optional)")


# --- Sub-models ---

class ActivityRef(BaseModel):
    name: str
    address: str = ""
    price_eur: float = 0
    duration_minutes: int = 0
    booking_url: str = ""
    booking_required: bool = False
    category: str = ""


class Tension(BaseModel):
    type: str = Field(default="none", description="complication | revelation | choix_sous_pression | bifurcation | risque_calcule | none")
    description: str = ""
    resolution: str = ""


class CameraMode(BaseModel):
    enabled: bool = False
    purpose: str = ""


class ContextualMusic(BaseModel):
    enabled: bool = False
    track_type: str = ""
    duration_seconds: int = 0


class RayBanVersion(BaseModel):
    script: str = ""
    duration_seconds: int = 20
    audio_type: str = Field(default="narration", description="narration | whisper")
    camera_mode: CameraMode = Field(default_factory=CameraMode)
    contextual_music: ContextualMusic = Field(default_factory=ContextualMusic)


class CharacterInteraction(BaseModel):
    character: str = ""
    trigger: str = ""
    phone_version: str = ""
    rayban_version: RayBanVersion = Field(default_factory=RayBanVersion)
    awaits_response: bool = True


class Verification(BaseModel):
    method: str = Field(default="zk_location", description="zk_location | camera_ai | text_answer")
    target: str = ""
    success_condition: str = ""
    success_reaction: str = Field(default="", description="Narrative reaction if the player succeeds")
    failure_fallback: str = Field(default="", description="What happens if the player fails — the story ALWAYS continues")
    timeout_reaction: str = Field(default="", description="Character message if the player takes too long")


class Step(BaseModel):
    step_id: int
    is_collaborative: bool = False
    is_skill_step: bool = False
    title: str = ""
    activity: ActivityRef = Field(default_factory=ActivityRef)
    narrative_intro: str = ""
    instruction: str = ""
    tension: Tension = Field(default_factory=Tension)
    character_interactions: list[CharacterInteraction] = Field(default_factory=list)
    verification: Verification = Field(default_factory=Verification)
    walking_minutes_from_previous: int = Field(default=0, description="Walking minutes from previous step (max 5)")
    player_action: str = Field(default="", description="Concrete action the player performs at this step")
    gps_trigger: dict = Field(default_factory=dict, description="Content unlocked by GPS proximity")
    camera_prompt: str = Field(default="", description="What to photograph and how AI interprets it")
    blockchain_event: str | None = None
    unlock_message: str = ""
    skill_xp: int = 0


# --- Characters ---

class MemoryState(BaseModel):
    trust_level: int = 50
    ignored_count: int = 0
    interaction_count: int = 0
    tone_of_responses: str = "sincere"
    dormant: bool = False


class Character(BaseModel):
    name: str
    age: int = 0
    type: str = Field(default="principal", description="principal | secondary | invoked")
    archetype: str = Field(default="", description="mastermind | electron_libre | genie_arrogant | fantome | love_interest")
    personality: str = ""
    speech_pattern: str = Field(default="", description="Distinctive speech quirks, examples of typical lines")
    relationship_to_player: str = Field(default="", description="How this character perceives the player initially")
    secret: str = ""
    evolution_rules: str = Field(default="", description="How this character changes based on player behavior")
    reactions_imprevues: str = Field(default="", description="How this character handles the unexpected, their red lines")
    voice_id: str = "elevenlabs_placeholder"
    memory_state: MemoryState = Field(default_factory=MemoryState)
    unlock_conditions: list[str] = Field(default_factory=list)
    system_prompt: str = Field(default="", description="Full system prompt for Character Runtime")


# --- Pre-Quest Bundle ---

class EmailBundle(BaseModel):
    from_character: str = ""
    subject: str = ""
    body: str = ""


class VoicemailBundle(BaseModel):
    from_character: str = ""
    script: str = ""
    duration_seconds: int = 30


class PdfBundle(BaseModel):
    type: str = ""
    content_brief: str = ""


class PlaylistBundle(BaseModel):
    name: str = ""
    mood: str = ""
    genre_keywords: list[str] = Field(default_factory=list)


class PreQuestBundle(BaseModel):
    email: EmailBundle = Field(default_factory=EmailBundle)
    voicemail: VoicemailBundle = Field(default_factory=VoicemailBundle)
    pdf: PdfBundle = Field(default_factory=PdfBundle)
    playlist: PlaylistBundle = Field(default_factory=PlaylistBundle)


# --- Narrative Universe ---

class NarrativeUniverse(BaseModel):
    hook: str = Field(description="Irresistible hook — presupposes an existing role")
    context: str = ""
    protagonist: str = ""
    stakes: str = ""


# --- Budget ---

class BudgetConfirmed(BaseModel):
    total: float = 0
    pre_quest: float = 0
    activities: float = 0
    reward: float = 0
    within_budget: bool = True


# --- Decision Tree ---

class Decision(BaseModel):
    step_id: int = 0
    prompt: str = ""
    options: list[str] = Field(default_factory=list)
    consequence: str = ""


class Ending(BaseModel):
    condition: str = ""
    narrative: str = ""
    reward: str = ""
    cost_eur: float = 0


class DecisionTree(BaseModel):
    decisions: list[Decision] = Field(default_factory=list)
    endings: dict[str, Ending] = Field(default_factory=dict)
    trust_consequences: dict[str, dict] = Field(default_factory=dict, description="Per-character trust changes based on player actions: {char_name: {obey: +10, betray: -30, flirt: +5, ignore: -10}}")


# --- Narrative Beats (flexible story moments for the orchestrator) ---

class NarrativeBeat(BaseModel):
    beat_id: int = 0
    description: str = Field(description="What happens narratively at this beat")
    characters_involved: list[str] = Field(default_factory=list)
    earliest_step: int = Field(default=0, description="Earliest step this can happen")
    latest_step: int = Field(default=99, description="Latest step before this must happen")
    tension_level: str = Field(default="medium", description="low | medium | high | climax")
    can_be_skipped: bool = False
    possible_triggers: list[str] = Field(default_factory=list, description="Player actions that could trigger this beat")


# --- Generation Meta ---

class GenerationMeta(BaseModel):
    scout_direction_chosen: str = ""
    storyteller_curator_iterations: int = 0
    judge_iterations: int = 0
    judge_final_score: int = 0


# --- Character System ---

class CharacterSystem(BaseModel):
    max_active: int = 15
    principals: list[str] = Field(default_factory=list)


# --- Resolution ---

class NftMetadata(BaseModel):
    city: str = ""
    date: str = ""
    quest_title: str = ""
    characters_met: list[str] = Field(default_factory=list)
    ending_chosen: str = ""


class Prize(BaseModel):
    xp_total: int = 0
    token_amount: int = 0
    nft_metadata: NftMetadata = Field(default_factory=NftMetadata)


class Resolution(BaseModel):
    skill_gained: str = ""
    prize: Prize = Field(default_factory=Prize)


# --- Final Quest Output ---

class QuestOutput(BaseModel):
    quest_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    tone: str = "loufoque"
    player_name: str = Field(default="", description="Player's first name — characters call them by their real first name")
    generation_meta: GenerationMeta = Field(default_factory=GenerationMeta)
    pre_quest_bundle: PreQuestBundle = Field(default_factory=PreQuestBundle)
    narrative_universe: NarrativeUniverse
    character_system: CharacterSystem = Field(default_factory=CharacterSystem)
    characters: list[Character] = Field(default_factory=list)
    budget_confirmed: BudgetConfirmed = Field(default_factory=BudgetConfirmed)
    steps: list[Step] = Field(default_factory=list)
    narrative_beats: list[NarrativeBeat] = Field(default_factory=list, description="Flexible story moments the orchestrator can place dynamically")
    narrative_tensions: list[str] = Field(default_factory=list, description="Forces/dilemmas at play — not predefined endings")
    twist: dict = Field(default_factory=dict, description="Central twist + revelation_variants")
    resolution_principles: list[str] = Field(default_factory=list, description="Rules for building the ending at runtime")
    trust_dynamics: dict[str, dict] = Field(default_factory=dict, description="Per-character behavior by trust level (low/medium/high)")
    resolution: Resolution = Field(default_factory=Resolution)

    # Booking-relevant fields — copied from QuestRequest so they survive generation
    quest_datetime: str = Field(default="", description="When the quest starts, from QuestRequest.datetime")
    quest_players: int = Field(default=1, description="Number of players, from QuestRequest.players")
    quest_budget: float = Field(default=0, description="Budget in EUR, from QuestRequest.budget")
    player_email: str = Field(default="", description="Player email for booking forms")

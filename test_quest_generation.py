"""Test script — generate a quest from the existing Cannes CityContext."""

import asyncio
import json
from agents.city_research.models import CityContext
from agents.quest_generation.models import QuestRequest
from agents.quest_generation.pipeline import generate_quest


async def main():
    # Load existing CityContext from research
    with open("result.json", "r", encoding="utf-8") as f:
        city_data = json.load(f)
    city_context = CityContext(**city_data)

    # Quest request
    request = QuestRequest(
        goal="sport + découverte",
        vibe="mystère, aventure",
        duration="4h",
        budget=50,
        location="Cannes",
        difficulty="life-maxing",
        players=1,
        datetime="2026-04-05 10:00",
        tone="loufoque",
        skill="exploration urbaine",
    )

    print("=" * 60)
    print("OpenD&D — Quest Generation Test")
    print("=" * 60)
    print(f"Tone: {request.tone} | Skill: {request.skill}")
    print(f"Budget: {request.budget}€ | Duration: {request.duration}")
    print(f"City: {request.location} ({len(city_context.activities)} activities loaded)")
    print("=" * 60)

    quest = await generate_quest(request, city_context)

    # Write output
    result_json = quest.model_dump_json(indent=2)
    with open("quest_output.json", "w", encoding="utf-8") as f:
        f.write(result_json)

    print(f"\nQuest written to quest_output.json")
    print(f"Title: {quest.title}")
    print(f"Steps: {len(quest.steps)}")
    print(f"Characters: {len(quest.characters)}")
    print(f"Score: {quest.generation_meta.judge_final_score}/100")


if __name__ == "__main__":
    asyncio.run(main())

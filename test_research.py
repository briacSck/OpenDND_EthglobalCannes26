"""Quick test script — run the City Research Agent on a Cannes quest."""

import asyncio
import json
from agents.city_research.agent import CityResearchAgent


async def main():
    agent = CityResearchAgent()

    request = {
        "goal": "sport + découverte",
        "vibe": "mystère, aventure",
        "duration": "4h",
        "budget": 50,
        "location": "Cannes",
        "difficulty": "life-maxing",
        "players": 1,
        "datetime": "2026-04-05 10:00",
    }

    print("=" * 60)
    print("OpenD&D — City Research Agent Test")
    print("=" * 60)
    print(f"Request: {json.dumps(request, ensure_ascii=False, indent=2)}")
    print("=" * 60)

    context = await agent.research(request)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    result_json = context.model_dump_json(indent=2)
    # Write to file to avoid Windows encoding issues
    with open("result.json", "w", encoding="utf-8") as f:
        f.write(result_json)
    total = len(context.activities) + len(context.restaurants) + len(context.shops) + len(context.events) + len(context.points_of_interest)
    print(f"Results written to result.json ({len(context.activities)} activities, {len(context.restaurants)} restaurants, {len(context.shops)} shops, {len(context.events)} events, {len(context.points_of_interest)} POIs) — {total} TOTAL")


if __name__ == "__main__":
    asyncio.run(main())

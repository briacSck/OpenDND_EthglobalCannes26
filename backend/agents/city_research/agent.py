"""City Research Agent — orchestrates iterative web research via Claude tool use.

The LLM decides WHICH searches to run. Results are collected raw and aggregated
in Python — no expensive LLM compile step.
"""

from __future__ import annotations

import json
import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

from agents.city_research.models import (
    CityContext, LocationInfo, Activity, Restaurant, Shop, Event, POI,
    TransportInfo, NewsItem,
)
from agents.city_research.tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS
from agents.city_research.prompts import CITY_RESEARCH_SYSTEM_PROMPT

load_dotenv()

MAX_ITERATIONS = 8


class CityResearchAgent:
    def __init__(self):
        self.client = AsyncAnthropic(
            base_url=os.getenv("ANTHROPIC_BASE_URL"),
            api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
            max_retries=5,
        )
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        self.tools = TOOL_DEFINITIONS

    async def research(self, quest_request: dict) -> CityContext:
        """Run the iterative research loop and return a CityContext."""

        user_prompt = self._build_user_prompt(quest_request)
        messages = [{"role": "user", "content": user_prompt}]

        # Collect raw results by tool type
        raw_results: dict[str, list[str]] = {
            "google": [],
            "tripadvisor": [],
            "google_maps": [],
            "luma": [],
            "getyourguide": [],
            "news": [],
            "weather": [],
            "directions": [],
        }

        for i in range(MAX_ITERATIONS):
            print(f"\n--- Agent iteration {i + 1} ---", flush=True)

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                system=CITY_RESEARCH_SYSTEM_PROMPT,
                tools=self.tools,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                assistant_content = response.content
                tool_results = []

                for block in assistant_content:
                    if block.type == "text":
                        print(f"Agent: {block.text[:200]}...", flush=True)
                    elif block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input

                        print(f"  -> {tool_name}({json.dumps(tool_input, ensure_ascii=False)[:80]})", flush=True)

                        result = await self._execute_tool(tool_name, tool_input)
                        print(f"  <- {len(result)} chars", flush=True)

                        # Store raw result
                        key = tool_name.replace("search_", "")
                        if key in raw_results:
                            raw_results[key].append(result)
                        else:
                            raw_results.setdefault("other", []).append(result)

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason in ("end_turn", "max_tokens"):
                for block in response.content:
                    if block.type == "text":
                        print(f"Agent done: {block.text[:200]}", flush=True)
                break

        # Aggregate raw results into CityContext — no LLM needed
        print("\n--- Aggregating results (no LLM) ---", flush=True)
        city = quest_request.get("location", "Unknown")
        context = self._aggregate(city, raw_results)
        print(f"Done: {len(context.activities)} activities, {len(context.restaurants)} restaurants, "
              f"{len(context.points_of_interest)} POIs, {len(context.current_news)} news", flush=True)
        return context

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        func = TOOL_FUNCTIONS.get(tool_name)
        if not func:
            return f"Error: unknown tool '{tool_name}'"
        try:
            result = await func(**tool_input)
            if len(result) > 5000:
                result = result[:5000] + "\n[... truncated]"
            return result
        except Exception as e:
            return f"Error calling {tool_name}: {e}"

    def _build_user_prompt(self, quest_request: dict) -> str:
        tone = quest_request.get("tone", "loufoque")
        news_instruction = ""
        if tone == "high_stakes":
            news_instruction = (
                "\n**HIGH_STAKES** — Use search_news to find current scandals, "
                "judicial affairs, geopolitical events near this location. "
                "Find 5-10 real news items for narrative anchoring."
            )

        return f"""Research this location for a quest:

- **Location**: {quest_request.get('location', 'Cannes')}
- **Goal**: {quest_request.get('goal', 'general discovery')}
- **Vibe**: {quest_request.get('vibe', 'aventure')}
- **Duration**: {quest_request.get('duration', '4h')}
- **Budget**: {quest_request.get('budget', 50)}€
- **Date/Time**: {quest_request.get('datetime', 'tomorrow 10:00')}
- **Tone**: {tone}
{news_instruction}

Search across Google, TripAdvisor, Google Maps, Luma, GetYourGuide.
Find: activities, restaurants, events, points of interest, transport info.
When you have enough data (4-6 iterations), just stop — say "DONE" and summarize what you found.
Do NOT try to compile or structure the results — just search."""

    def _aggregate(self, city: str, raw: dict[str, list[str]]) -> CityContext:
        """Parse raw search results into a CityContext. Best-effort extraction."""

        all_text = ""
        for source, results in raw.items():
            for r in results:
                all_text += f"\n[{source}] {r}\n"

        # Weather
        weather = ""
        for w in raw.get("weather", []):
            weather = w.strip()

        # Directions / transport
        directions_notes = "\n".join(raw.get("directions", []))

        # News items from search_news results
        news_items = []
        for news_text in raw.get("news", []):
            # Each news result is raw text — store as one NewsItem per result block
            if news_text and len(news_text) > 20:
                # Try to extract individual items from the text
                for line in news_text.split("\n"):
                    line = line.strip()
                    if len(line) > 30 and not line.startswith("Error"):
                        news_items.append(NewsItem(
                            name=line[:120],
                            summary=line,
                            source="search_news",
                        ))

        return CityContext(
            location=LocationInfo(city=city, weather=weather),
            city_description=f"Raw research data for {city}. See raw_notes for full details.",
            activities=[],
            restaurants=[],
            shops=[],
            events=[],
            points_of_interest=[],
            transport=TransportInfo(notes=directions_notes),
            current_news=news_items[:15],
            raw_notes=all_text[:50000],  # Cap at 50k chars
        )

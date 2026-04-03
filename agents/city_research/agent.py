"""City Research Agent — orchestrates iterative web research via Claude tool use."""

from __future__ import annotations

import json
import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

from agents.city_research.models import CityContext
from agents.city_research.tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS
from agents.city_research.prompts import CITY_RESEARCH_SYSTEM_PROMPT, COMPILE_RESULTS_TOOL

load_dotenv()

MAX_ITERATIONS = 20  # safety cap on tool use loops
FORCE_COMPILE_AT = 10  # force compile after this many iterations


class CityResearchAgent:
    def __init__(self):
        self.client = AsyncAnthropic(
            base_url=os.getenv("ANTHROPIC_BASE_URL"),
            api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
        )
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        # All tools: search tools + compile_results
        self.tools = TOOL_DEFINITIONS + [COMPILE_RESULTS_TOOL]

    async def research(self, quest_request: dict) -> CityContext:
        """Run the iterative research loop and return a CityContext."""

        user_prompt = self._build_user_prompt(quest_request)
        messages = [{"role": "user", "content": user_prompt}]

        for i in range(MAX_ITERATIONS):
            print(f"\n--- Agent iteration {i + 1} ---")

            # Force compilation if taking too long
            if i == FORCE_COMPILE_AT:
                print("  -> Forcing compilation (iteration limit)...")
                messages.append({
                    "role": "user" if messages[-1]["role"] == "assistant" else "user",
                    "content": "STOP SEARCHING. You've done enough research. Call compile_results NOW with at least 50 entries total, using your search results AND your own verified knowledge of the city. Include 15+ activities, 10+ restaurants, 5+ shops, 5+ events, 10+ POIs.",
                })

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                system=CITY_RESEARCH_SYSTEM_PROMPT,
                tools=self.tools,
                messages=messages,
            )

            # Check if the model wants to use tools
            if response.stop_reason == "tool_use":
                # Process all tool calls in this response
                assistant_content = response.content
                tool_results = []

                for block in assistant_content:
                    if block.type == "text":
                        print(f"Agent: {block.text[:200]}...")
                    elif block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input

                        print(f"  -> Calling {tool_name}({json.dumps(tool_input, ensure_ascii=False)[:100]})")

                        # If compile_results is called, we're done
                        if tool_name == "compile_results":
                            print("  -> Research complete! Compiling results...")
                            return self._parse_city_context(tool_input)

                        # Execute the search tool
                        result = await self._execute_tool(tool_name, tool_input)
                        print(f"  <- Got {len(result)} chars of results")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                # Add assistant message and tool results to conversation
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "end_turn":
                # Model finished without compile_results — extract any text and nudge it
                for block in response.content:
                    if block.type == "text":
                        print(f"Agent (final): {block.text[:300]}")

                # Nudge to compile
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": "You've done great research. Now please call the compile_results tool to structure your findings into the final CityContext.",
                })
            elif response.stop_reason == "max_tokens":
                # Response was cut off — may have incomplete tool_use blocks
                print("  -> Hit max_tokens, recovering...")

                # Filter out any tool_use blocks and provide dummy results so the API doesn't complain
                assistant_content = response.content
                dangling_tool_ids = [
                    block.id for block in assistant_content if block.type == "tool_use"
                ]

                if dangling_tool_ids:
                    # Must provide tool_results for any tool_use in the truncated response
                    messages.append({"role": "assistant", "content": assistant_content})
                    dummy_results = [
                        {
                            "type": "tool_result",
                            "tool_use_id": tid,
                            "content": "[skipped — response was truncated]",
                        }
                        for tid in dangling_tool_ids
                    ]
                    messages.append({"role": "user", "content": dummy_results + [
                        {"type": "text", "text": "Your previous response was truncated. Please immediately call compile_results with everything you've found so far. Do NOT do more searches."}
                    ]})
                else:
                    messages.append({"role": "assistant", "content": assistant_content})
                    messages.append({
                        "role": "user",
                        "content": "Your response was truncated. Please immediately call compile_results with everything you've found so far. Do NOT do more searches.",
                    })
            else:
                print(f"Unexpected stop reason: {response.stop_reason}")
                break

        raise RuntimeError(f"Agent did not complete after {MAX_ITERATIONS} iterations")

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a search tool and return its result as a string."""
        func = TOOL_FUNCTIONS.get(tool_name)
        if not func:
            return f"Error: unknown tool '{tool_name}'"
        try:
            result = await func(**tool_input)
            # Truncate very long results to keep context manageable
            if len(result) > 5000:
                result = result[:5000] + "\n\n[... truncated — use more specific queries for details]"
            return result
        except Exception as e:
            return f"Error calling {tool_name}: {e}"

    def _build_user_prompt(self, quest_request: dict) -> str:
        """Build the initial user prompt from a quest request."""
        return f"""Here is the quest request from the user:

- **Goal**: {quest_request.get('goal', 'general discovery')}
- **Vibe**: {quest_request.get('vibe', 'aventure')}
- **Duration**: {quest_request.get('duration', '4h')}
- **Budget**: {quest_request.get('budget', 50)}€
- **Location**: {quest_request.get('location', 'Cannes')}
- **Difficulty**: {quest_request.get('difficulty', 'life-maxing')}
- **Players**: {quest_request.get('players', 1)}
- **Date/Time**: {quest_request.get('datetime', 'tomorrow 10:00')}
- **Tone**: {quest_request.get('tone', 'loufoque')}

{"**IMPORTANT: This is a HIGH_STAKES quest.** You MUST research current news, scandals, geopolitical events, and judicial affairs related to this location using the search_news tool. Find at least 5-10 real, verifiable news items that could anchor a Da Vinci Code / Mission Impossible style narrative. The player must be able to Google these and find real articles." if quest_request.get('tone') == 'high_stakes' else ""}

Start your research! Remember:
1. First do a broad search across multiple sources (Google, TripAdvisor, Google Maps, Luma, GetYourGuide)
2. Analyze what you found and identify gaps
3. Do targeted searches to fill the gaps
4. Call compile_results with your structured findings

Scope your searches to the specific area and constraints above. Go!"""

    def _parse_city_context(self, raw: dict) -> CityContext:
        """Parse the compile_results tool input into a CityContext model."""
        from agents.city_research.models import (
            LocationInfo, Activity, Restaurant, Shop, Event, POI, TransportInfo, NewsItem,
        )

        location = LocationInfo(**raw.get("location", {"city": "Unknown"}))

        activities = [Activity(**a) for a in raw.get("activities", [])]
        restaurants = [Restaurant(**r) for r in raw.get("restaurants", [])]
        shops = [Shop(**s) for s in raw.get("shops", [])]
        events = [Event(**e) for e in raw.get("events", [])]
        pois = [POI(**p) for p in raw.get("points_of_interest", [])]
        news = [NewsItem(**n) for n in raw.get("current_news", [])]

        transport_data = raw.get("transport", {})
        transport = TransportInfo(**transport_data) if transport_data else TransportInfo()

        return CityContext(
            location=location,
            city_description=raw.get("city_description", ""),
            activities=activities,
            restaurants=restaurants,
            shops=shops,
            events=events,
            points_of_interest=pois,
            transport=transport,
            current_news=news,
            raw_notes=raw.get("raw_notes", ""),
        )

"""Curator Agent — manages real activities catalog + live search, guarantees budget."""

from __future__ import annotations

import json
import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

from agents.city_research.models import CityContext
from agents.city_research.tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS
from agents.quest_generation.prompts import build_curator_prompt

load_dotenv()


def log(msg: str):
    print(msg, flush=True)


MAX_TOOL_ITERATIONS = 4


class CuratorAgent:
    def __init__(self, city_context: CityContext, budget: float):
        self.client = AsyncAnthropic(
            base_url=os.getenv("ANTHROPIC_BASE_URL"),
            api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
        )
        self.model = os.getenv("CURATOR_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"))
        self.city_context = city_context
        self.budget = budget

        # Build news JSON if available
        news_json = ""
        if city_context.current_news:
            news_json = json.dumps([n.model_dump() for n in city_context.current_news], ensure_ascii=False, indent=2)

        # Build system prompt with real data injected
        self.system_prompt = build_curator_prompt(
            city=city_context.location.city,
            budget=budget,
            activities_json=json.dumps([a.model_dump() for a in city_context.activities], ensure_ascii=False, indent=2),
            restaurants_json=json.dumps([r.model_dump() for r in city_context.restaurants], ensure_ascii=False, indent=2),
            events_json=json.dumps([e.model_dump() for e in city_context.events], ensure_ascii=False, indent=2),
            pois_json=json.dumps([p.model_dump() for p in city_context.points_of_interest], ensure_ascii=False, indent=2),
            transport_json=json.dumps(city_context.transport.model_dump(), ensure_ascii=False, indent=2),
            news_json=news_json,
        )

        # Live search tools from city_research
        self.tools = TOOL_DEFINITIONS

    async def respond(self, storyteller_request: str) -> str:
        """Respond to a Storyteller request with real activities + budget tracking."""

        messages = [{"role": "user", "content": storyteller_request}]

        for _ in range(MAX_TOOL_ITERATIONS):
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                system=self.system_prompt,
                tools=self.tools,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                # Execute search tools and continue
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        log(f"  [Curator] Searching: {block.name}({json.dumps(block.input, ensure_ascii=False)[:80]})")
                        result = await self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result[:2000],
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                # Extract text response
                return self._extract_text(response)

        return "[Curator] Recherche terminée — voici ce que j'ai trouvé dans le catalogue existant."

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        func = TOOL_FUNCTIONS.get(tool_name)
        if not func:
            return f"Outil inconnu: {tool_name}"
        try:
            result = await func(**tool_input)
            return result
        except Exception as e:
            return f"Erreur: {e}"

    def _extract_text(self, response) -> str:
        parts = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)
        return "\n".join(parts)

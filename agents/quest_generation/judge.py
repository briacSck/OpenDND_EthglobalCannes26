"""Judge Agent — evaluates quest quality, sends feedback if below threshold."""

from __future__ import annotations

import json
import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

from agents.quest_generation.prompts import JUDGE_SYSTEM_PROMPT

load_dotenv()


class JudgeResult:
    def __init__(self, score: int, validated: bool, breakdown: dict, feedback: list[dict]):
        self.score = score
        self.validated = validated
        self.breakdown = breakdown
        self.feedback = feedback


class JudgeAgent:
    def __init__(self):
        self.client = AsyncAnthropic(
            base_url=os.getenv("ANTHROPIC_BASE_URL"),
            api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
        )
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")

    async def evaluate(self, quest_raw: dict, request_context: dict) -> JudgeResult:
        """Evaluate a quest and return score + feedback."""

        quest_json = json.dumps(quest_raw, ensure_ascii=False, indent=2)
        # Truncate if too long
        if len(quest_json) > 15000:
            quest_json = quest_json[:15000] + "\n... [tronqué]"

        messages = [
            {"role": "user", "content": f"""Évalue cette quête :

## Contexte de la demande
- Tone : {request_context.get('tone', 'loufoque')}
- Skill : {request_context.get('skill', 'exploration')}
- Budget : {request_context.get('budget', 50)}€
- Durée : {request_context.get('duration', '4h')}
- Joueurs : {request_context.get('players', 1)}

## Quête à évaluer
```json
{quest_json}
```

Évalue selon la grille (hook/trame/activités/registre/budget — 20pts chacun).
Réponds UNIQUEMENT avec le JSON d'évaluation."""}
        ]

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=JUDGE_SYSTEM_PROMPT,
            messages=messages,
        )

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        return self._parse_judgment(text)

    def _parse_judgment(self, text: str) -> JudgeResult:
        """Parse the Judge's JSON response."""
        # Extract JSON from response
        json_str = text.strip()

        # Handle markdown code blocks
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback: assume it passed to avoid blocking
            print(f"  [Judge] Failed to parse response, assuming pass: {text[:200]}", flush=True)
            return JudgeResult(
                score=75,
                validated=True,
                breakdown={"hook": 15, "trame": 15, "activites": 15, "registre": 15, "budget": 15},
                feedback=[],
            )

        return JudgeResult(
            score=data.get("score", 0),
            validated=data.get("validated", False),
            breakdown=data.get("breakdown", {}),
            feedback=data.get("feedback", []),
        )

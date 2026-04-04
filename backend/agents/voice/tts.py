"""ElevenLabs TTS — streaming text-to-speech + voice generation."""

from __future__ import annotations

import os
import asyncio
import json
from typing import AsyncIterator

import httpx
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"


class ElevenLabsTTS:
    """Streaming TTS client for ElevenLabs."""

    def __init__(self, voice_id: str, model_id: str = "eleven_multilingual_v2"):
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.voice_id = voice_id
        self.model_id = model_id
        self._headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def stream(self, text_iterator: AsyncIterator[str]) -> AsyncIterator[bytes]:
        """Stream text chunks into ElevenLabs and yield audio MP3 chunks.

        Uses the input streaming endpoint: text chunks are sent as they arrive
        from Claude, and audio chunks come back as soon as ElevenLabs has enough
        text to synthesize.
        """
        url = f"{ELEVENLABS_BASE}/text-to-speech/{self.voice_id}/stream"

        # Collect text chunks, flush to ElevenLabs in sentence-sized batches
        # for low latency. ElevenLabs streaming input expects the full text
        # via the standard streaming endpoint.
        buffer = ""
        sentence_enders = {".", "!", "?", "…", "\n"}

        async def flush_buffer(text: str) -> AsyncIterator[bytes]:
            if not text.strip():
                return
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=self._headers,
                    json={
                        "text": text,
                        "model_id": self.model_id,
                        "voice_settings": {
                            "stability": 0.5,
                            "similarity_boost": 0.75,
                            "style": 0.4,
                        },
                    },
                )
                response.raise_for_status()
                # Yield the entire audio chunk for this sentence
                yield response.content

        async for text_chunk in text_iterator:
            buffer += text_chunk
            # Flush when we hit a sentence boundary
            while buffer:
                # Find the earliest sentence ender
                earliest = -1
                for ender in sentence_enders:
                    pos = buffer.find(ender)
                    if pos != -1 and (earliest == -1 or pos < earliest):
                        earliest = pos
                if earliest == -1:
                    break
                sentence = buffer[: earliest + 1]
                buffer = buffer[earliest + 1 :]
                async for chunk in flush_buffer(sentence):
                    yield chunk

        # Flush remaining text
        if buffer.strip():
            async for chunk in flush_buffer(buffer):
                yield chunk

    async def synthesize(self, text: str) -> bytes:
        """One-shot TTS: convert full text to audio bytes."""
        url = f"{ELEVENLABS_BASE}/text-to-speech/{self.voice_id}/stream"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers=self._headers,
                json={
                    "text": text,
                    "model_id": self.model_id,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "style": 0.4,
                    },
                },
            )
            response.raise_for_status()
            return response.content

    @staticmethod
    async def generate_voice(description: str) -> str:
        """Use ElevenLabs Voice Design API to create a voice from a text description.

        Args:
            description: Natural language description of the voice
                (e.g. "Italian man, 60s, warm baritone, slight accent, confident")

        Returns:
            The generated voice_id.
        """
        api_key = os.getenv("ELEVENLABS_API_KEY", "")
        url = f"{ELEVENLABS_BASE}/text-to-voice/create-previews"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "voice_description": description,
                    "text": "Hello, this is a test of my voice. I hope you find it convincing and natural. Let me tell you something important about what happened yesterday evening near the old harbour.",
                },
            )
            response.raise_for_status()
            data = response.json()

        # The API returns previews — pick the first one and save it
        previews = data.get("previews", [])
        if not previews:
            raise RuntimeError("ElevenLabs returned no voice previews")

        # Create a permanent voice from the first preview
        preview_id = previews[0]["generated_voice_id"]
        save_url = f"{ELEVENLABS_BASE}/text-to-voice/create-voice-from-preview"

        async with httpx.AsyncClient(timeout=30.0) as client:
            save_resp = await client.post(
                save_url,
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "voice_name": f"quest_char_{preview_id[:8]}",
                    "voice_description": description[:200],
                    "generated_voice_id": preview_id,
                },
            )
            save_resp.raise_for_status()
            voice_data = save_resp.json()

        return voice_data["voice_id"]

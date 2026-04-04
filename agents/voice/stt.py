"""Deepgram STT — streaming speech-to-text with endpoint detection."""

from __future__ import annotations

import os
import asyncio
import json
from typing import AsyncIterator, Callable

import httpx
from dotenv import load_dotenv

load_dotenv()

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"


class DeepgramSTT:
    """Streaming STT client using Deepgram's WebSocket API."""

    def __init__(
        self,
        language: str = "fr",
        sample_rate: int = 16000,
        encoding: str = "linear16",
    ):
        self.api_key = os.getenv("DEEPGRAM_API_KEY", "")
        self.language = language
        self.sample_rate = sample_rate
        self.encoding = encoding

    async def transcribe(
        self,
        audio_stream: AsyncIterator[bytes],
        on_partial: Callable[[str], None] | None = None,
    ) -> AsyncIterator[str]:
        """Stream audio chunks to Deepgram, yield final transcriptions.

        Args:
            audio_stream: Async iterator of raw PCM audio bytes.
            on_partial: Optional callback for interim (partial) transcripts.

        Yields:
            Final transcription strings (one per utterance, after endpoint detection).
        """
        try:
            import websockets
        except ImportError:
            raise RuntimeError("Install websockets: pip install websockets")

        params = (
            f"?language={self.language}"
            f"&sample_rate={self.sample_rate}"
            f"&encoding={self.encoding}"
            f"&channels=1"
            f"&model=nova-2"
            f"&punctuate=true"
            f"&endpointing=300"  # 300ms silence = end of utterance
            f"&interim_results=true"
            f"&utterance_end_ms=1500"
        )

        url = DEEPGRAM_WS_URL + params
        headers = {"Authorization": f"Token {self.api_key}"}

        # Queue for yielding final transcripts back to the caller
        transcript_queue: asyncio.Queue[str | None] = asyncio.Queue()

        async with websockets.connect(url, additional_headers=headers) as ws:

            async def send_audio():
                """Forward audio chunks to Deepgram."""
                try:
                    async for chunk in audio_stream:
                        await ws.send(chunk)
                    # Signal end of audio
                    await ws.send(json.dumps({"type": "CloseStream"}))
                except Exception:
                    await ws.send(json.dumps({"type": "CloseStream"}))

            async def receive_transcripts():
                """Receive transcription results from Deepgram."""
                try:
                    async for message in ws:
                        data = json.loads(message)
                        msg_type = data.get("type", "")

                        if msg_type == "Results":
                            channel = data.get("channel", {})
                            alternatives = channel.get("alternatives", [])
                            if not alternatives:
                                continue

                            transcript = alternatives[0].get("transcript", "")
                            if not transcript:
                                continue

                            is_final = data.get("is_final", False)
                            speech_final = data.get("speech_final", False)

                            if is_final or speech_final:
                                await transcript_queue.put(transcript)
                            elif on_partial:
                                on_partial(transcript)

                        elif msg_type == "UtteranceEnd":
                            # Deepgram detected end of utterance
                            pass

                except Exception:
                    pass
                finally:
                    await transcript_queue.put(None)  # Signal done

            # Run send and receive concurrently
            send_task = asyncio.create_task(send_audio())
            recv_task = asyncio.create_task(receive_transcripts())

            try:
                while True:
                    transcript = await transcript_queue.get()
                    if transcript is None:
                        break
                    yield transcript
            finally:
                send_task.cancel()
                recv_task.cancel()
                try:
                    await send_task
                except (asyncio.CancelledError, Exception):
                    pass
                try:
                    await recv_task
                except (asyncio.CancelledError, Exception):
                    pass

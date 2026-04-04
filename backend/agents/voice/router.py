"""Voice WebSocket router — real-time STT → Claude → TTS pipeline."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agents.voice.stt import DeepgramSTT
from agents.voice.tts import ElevenLabsTTS
from agents.quest_runtime.models import PlayerAction

log = logging.getLogger(__name__)

router = APIRouter()

# These will be set by main.py at startup
_sessions: dict = {}
_orchestrators: dict = {}


def init_stores(sessions: dict, orchestrators: dict):
    """Called by main.py to share the in-memory stores."""
    global _sessions, _orchestrators
    _sessions = sessions
    _orchestrators = orchestrators


@router.websocket("/play/voice/{session_id}/{character_name}")
async def voice_ws(ws: WebSocket, session_id: str, character_name: str):
    """Bidirectional voice conversation with a character.

    Protocol:
        Client → Server:
            - Binary frames: raw PCM audio (16kHz, 16-bit, mono, little-endian)
            - Text frames (JSON):
                {"type": "end_audio"}   — explicit end-of-speech signal
                {"type": "interrupt"}   — cut the character's current response

        Server → Client:
            - Text frames (JSON):
                {"type": "transcript", "text": "...", "is_final": true/false}
                {"type": "text_chunk", "text": "..."}
                {"type": "voice_chunk", "audio": "<base64 mp3>", "format": "mp3"}
                {"type": "end_turn"}
                {"type": "error", "message": "..."}
    """
    await ws.accept()

    # Validate session and character
    session = _sessions.get(session_id)
    if not session or not session.active:
        await ws.send_json({"type": "error", "message": "Session not found or inactive."})
        await ws.close()
        return

    orchestrator = _orchestrators.get(session_id)
    if not orchestrator:
        await ws.send_json({"type": "error", "message": "Orchestrator not found."})
        await ws.close()
        return

    char_agent = orchestrator.get_character_agent(character_name)
    if not char_agent:
        await ws.send_json({"type": "error", "message": f"Character '{character_name}' not found."})
        await ws.close()
        return

    # Get the character's ElevenLabs voice_id
    voice_id = char_agent.character.voice_id
    if not voice_id or voice_id == "elevenlabs_placeholder":
        await ws.send_json({"type": "error", "message": "Character has no voice configured."})
        await ws.close()
        return

    stt = DeepgramSTT(language="fr")
    tts = ElevenLabsTTS(voice_id=voice_id)

    interrupted = asyncio.Event()

    try:
        while True:
            interrupted.clear()
            transcript = await _listen_turn(ws, stt, interrupted)
            if transcript is None:
                break  # Client disconnected
            if not transcript.strip():
                continue

            # Send final transcript to client
            await ws.send_json({"type": "transcript", "text": transcript, "is_final": True})

            # Stream Claude response → TTS → client
            await _respond_turn(ws, char_agent, tts, transcript, interrupted)

            # Notify orchestrator (fire-and-forget for follow-up events)
            asyncio.create_task(
                _notify_orchestrator(ws, orchestrator, session, character_name, transcript)
            )

    except WebSocketDisconnect:
        log.info("Voice WS disconnected: session=%s character=%s", session_id, character_name)
    except Exception as e:
        log.exception("Voice WS error: %s", e)
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


async def _listen_turn(
    ws: WebSocket, stt: DeepgramSTT, interrupted: asyncio.Event
) -> str | None:
    """Listen to the player's speech and return the full transcript.

    Returns None if the WebSocket is closed.
    """
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def audio_stream() -> AsyncIterator[bytes]:
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                return
            yield chunk

    # Collect audio from WebSocket and feed to STT
    stt_task: asyncio.Task | None = None
    final_transcript = ""

    async def run_stt():
        nonlocal final_transcript
        parts = []
        async for text in stt.transcribe(audio_stream()):
            parts.append(text)
            # Send interim transcript to client
            try:
                await ws.send_json({"type": "transcript", "text": text, "is_final": False})
            except Exception:
                pass
        final_transcript = " ".join(parts)

    stt_task = asyncio.create_task(run_stt())

    try:
        while True:
            message = await ws.receive()

            if message.get("type") == "websocket.disconnect":
                await audio_queue.put(None)
                return None

            if "bytes" in message and message["bytes"]:
                await audio_queue.put(message["bytes"])

            elif "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue

                if data.get("type") == "end_audio":
                    await audio_queue.put(None)
                    break
                elif data.get("type") == "interrupt":
                    interrupted.set()
                    await audio_queue.put(None)
                    break

    except WebSocketDisconnect:
        await audio_queue.put(None)
        return None

    # Wait for STT to finish processing
    await stt_task
    return final_transcript


async def _respond_turn(
    ws: WebSocket,
    char_agent,
    tts: ElevenLabsTTS,
    transcript: str,
    interrupted: asyncio.Event,
):
    """Stream the character's response as text + voice to the client."""

    # Async iterator that collects text from Claude for TTS
    text_queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def text_stream_for_tts() -> AsyncIterator[str]:
        while True:
            chunk = await text_queue.get()
            if chunk is None:
                return
            yield chunk

    async def stream_claude():
        """Get text chunks from Claude and forward them."""
        try:
            async for chunk in char_agent.respond_stream(transcript):
                if interrupted.is_set():
                    break
                await text_queue.put(chunk)
                # Also send text chunk for subtitles
                try:
                    await ws.send_json({"type": "text_chunk", "text": chunk})
                except Exception:
                    break
        finally:
            await text_queue.put(None)

    async def stream_tts():
        """Convert text stream to audio and send to client."""
        try:
            async for audio_chunk in tts.stream(text_stream_for_tts()):
                if interrupted.is_set():
                    break
                audio_b64 = base64.b64encode(audio_chunk).decode("ascii")
                try:
                    await ws.send_json({
                        "type": "voice_chunk",
                        "audio": audio_b64,
                        "format": "mp3",
                    })
                except Exception:
                    break
        except Exception as e:
            log.error("TTS streaming error: %s", e)

    # Run Claude and TTS concurrently — TTS consumes Claude's output
    claude_task = asyncio.create_task(stream_claude())
    tts_task = asyncio.create_task(stream_tts())

    await claude_task
    await tts_task

    if not interrupted.is_set():
        try:
            await ws.send_json({"type": "end_turn"})
        except Exception:
            pass


async def _notify_orchestrator(
    ws: WebSocket, orchestrator, session, character_name: str, transcript: str
):
    """Tell the orchestrator about the voice exchange so it can trigger follow-ups."""
    try:
        player_action = PlayerAction(
            type="voice",
            content=transcript,
            target_character=character_name,
        )
        followup_events = await orchestrator.react(
            trigger="player_message",
            player_action=player_action,
        )
        # Send any follow-up events to the client
        for event in followup_events:
            await ws.send_json({
                "type": "followup_event",
                "event": event.model_dump(),
            })
    except Exception as e:
        log.error("Orchestrator notification error: %s", e)

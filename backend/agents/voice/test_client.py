"""CLI test client for the voice WebSocket — simulates a mobile app.

Usage:
    python agents/voice/test_client.py --session <session_id> --character <name> [--host localhost:8000]

Requires: pip install sounddevice websockets
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import io

try:
    import sounddevice as sd
except ImportError:
    print("Install sounddevice: pip install sounddevice")
    sys.exit(1)

try:
    import websockets
except ImportError:
    print("Install websockets: pip install websockets")
    sys.exit(1)

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
CHUNK_DURATION_MS = 100  # send audio every 100ms
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)


async def main(session_id: str, character_name: str, host: str):
    uri = f"ws://{host}/play/voice/{session_id}/{character_name}"
    print(f"Connecting to {uri}...")

    async with websockets.connect(uri) as ws:
        print(f"Connected! Speak into your microphone. Press Ctrl+C to stop.\n")

        # Shared state
        recording = asyncio.Event()
        recording.set()  # Start recording immediately

        async def send_audio():
            """Capture microphone audio and send to server."""
            loop = asyncio.get_event_loop()
            audio_queue: asyncio.Queue[bytes] = asyncio.Queue()

            def audio_callback(indata, frames, time_info, status):
                if recording.is_set():
                    audio_queue.put_nowait(indata.tobytes())

            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=CHUNK_SAMPLES,
                callback=audio_callback,
            )

            with stream:
                while True:
                    chunk = await audio_queue.get()
                    await ws.send(chunk)

        async def receive_messages():
            """Receive and handle server messages."""
            audio_chunks: list[bytes] = []

            async for message in ws:
                try:
                    data = json.loads(message)
                except (json.JSONDecodeError, TypeError):
                    continue

                msg_type = data.get("type", "")

                if msg_type == "transcript":
                    is_final = data.get("is_final", False)
                    prefix = "[YOU]" if is_final else "[...]"
                    print(f"  {prefix} {data['text']}")

                    if is_final:
                        # Stop recording while character responds
                        recording.clear()
                        print()

                elif msg_type == "text_chunk":
                    # Print character text inline (no newline)
                    print(data["text"], end="", flush=True)

                elif msg_type == "voice_chunk":
                    audio_b64 = data.get("audio", "")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        audio_chunks.append(audio_bytes)

                elif msg_type == "end_turn":
                    print("\n")
                    # Play all collected audio
                    if audio_chunks:
                        await play_audio(b"".join(audio_chunks))
                        audio_chunks.clear()
                    # Resume recording
                    recording.set()
                    print("  [MIC] Listening...\n")

                elif msg_type == "followup_event":
                    event = data.get("event", {})
                    char = event.get("character", "?")
                    content = event.get("content", "")[:200]
                    print(f"\n  [FOLLOWUP from {char}] {content}\n")

                elif msg_type == "error":
                    print(f"\n  [ERROR] {data.get('message', '')}\n")

        # Signal end of speech after silence
        async def detect_silence():
            """Periodically send end_audio signal when user stops talking.

            Simple approach: after 2 seconds of the character responding,
            send end_audio to let the server know we're done.
            """
            while True:
                await asyncio.sleep(0.1)
                # The actual VAD is handled by Deepgram on the server side
                # This task is here for manual end_audio if needed

        print("  [MIC] Listening...\n")

        try:
            await asyncio.gather(
                send_audio(),
                receive_messages(),
            )
        except websockets.exceptions.ConnectionClosed:
            print("\nConnection closed.")


async def play_audio(mp3_data: bytes):
    """Play MP3 audio data through speakers."""
    try:
        # Try using pydub for MP3 decoding
        from pydub import AudioSegment

        segment = AudioSegment.from_mp3(io.BytesIO(mp3_data))
        samples = segment.get_array_of_samples()

        import numpy as np
        audio_array = np.array(samples, dtype="int16")
        if segment.channels == 2:
            audio_array = audio_array.reshape((-1, 2))

        sd.play(audio_array, samplerate=segment.frame_rate)
        sd.wait()
    except ImportError:
        print("  [AUDIO] Install pydub for MP3 playback: pip install pydub")
        print("  [AUDIO] (also needs ffmpeg installed)")
    except Exception as e:
        print(f"  [AUDIO] Playback error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice test client for OpenD&D")
    parser.add_argument("--session", required=True, help="Session ID")
    parser.add_argument("--character", required=True, help="Character name")
    parser.add_argument("--host", default="localhost:8000", help="Server host:port")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.session, args.character, args.host))
    except KeyboardInterrupt:
        print("\nBye!")

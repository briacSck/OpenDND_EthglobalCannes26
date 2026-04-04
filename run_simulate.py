"""Interactive quest simulation — terminal CLI.

Commands:
    @CharName: message      Text chat with a character
    /voice CharName         Voice mode: mic → STT → Claude → TTS
    /goto step N            Jump to step N, trigger GPS events
    /gps lat lon            Simulate GPS position
    /photo description      Simulate camera input (AI vision)
    /rayban description     Same as /photo (Ray-Ban Meta frame)
    /next                   Advance to next step
    /status                 Show current state
    /chars                  List all characters
    /quit                   Exit
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from datetime import datetime

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.stderr.reconfigure(encoding="utf-8")

# Ensure we run from the project root (where quest_highstakes.json lives)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from colorama import init as colorama_init, Fore, Style
colorama_init()

from agents.quest_generation.models import QuestOutput
from agents.quest_runtime.models import (
    QuestSession, SessionState, CharacterTrust, PlayerAction,
)
from agents.quest_runtime.orchestrator import OrchestratorAgent
from agents.quest_runtime.character_agent import CharacterAgent
from agents.artifact_renderer import ArtifactRenderer

# Character colors
CHAR_COLORS = [Fore.CYAN, Fore.MAGENTA, Fore.YELLOW, Fore.GREEN, Fore.RED]
SYS_COLOR = Style.DIM + Fore.WHITE
GPS_COLOR = Fore.CYAN + Style.BRIGHT
CAM_COLOR = Fore.BLUE + Style.BRIGHT
RESET = Style.RESET_ALL

char_color_map: dict[str, str] = {}


def cprint(color: str, prefix: str, text: str):
    """Print colored output."""
    print(f"{color}[{prefix}]{RESET} {text}")


def sys_print(text: str):
    cprint(SYS_COLOR, "system", text)


def char_print(name: str, text: str):
    color = char_color_map.get(name, Fore.WHITE)
    print(f"\n{color}{'━' * 60}")
    print(f"  {name}")
    print(f"{'━' * 60}{RESET}")
    print(text)
    print(f"{color}{'━' * 60}{RESET}\n")


async def event_print(event, renderer=None, quest=None):
    """Print an orchestrator event. If renderer is provided, generate artifact files."""
    if event.type == "character_message":
        char_print(event.character, event.content)
    elif event.type == "artifact":
        cprint(GPS_COLOR, f"artifact:{event.artifact.type if event.artifact else '?'}", event.content)
        # Generate real artifact file
        if renderer and quest and event.artifact:
            try:
                path = await renderer.render_artifact(event.artifact, quest)
                if path:
                    cprint(GPS_COLOR, "file", path)
                    try:
                        os.startfile(path)
                    except Exception:
                        pass
            except Exception as e:
                sys_print(f"Artifact render error: {e}")
    elif event.type == "timer":
        cprint(Fore.RED + Style.BRIGHT, f"timer:{event.timer_seconds}s", f"[{event.character}] {event.content}")
    elif event.type == "group_chat":
        cprint(Fore.YELLOW, "group", event.content)
    elif event.type == "forwarded_message":
        cprint(Fore.YELLOW + Style.DIM, "intercepted", event.content)
    else:
        cprint(SYS_COLOR, event.type, event.content)


# --- TTS playback ---

async def play_tts(voice_id: str, text: str):
    """Synthesize and play character voice."""
    if not voice_id or voice_id == "elevenlabs_placeholder":
        return
    if not os.getenv("ELEVENLABS_API_KEY"):
        return
    try:
        from agents.voice.tts import ElevenLabsTTS
        tts = ElevenLabsTTS(voice_id=voice_id)
        sys_print("Generating voice...")
        audio = await tts.synthesize(text)
        # Write to temp file and play
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio)
            tmp_path = f.name
        os.startfile(tmp_path)
    except Exception as e:
        sys_print(f"TTS error: {e}")


# --- Voice recording ---

def _find_mic_device():
    """Find the best working input device."""
    import sounddevice as sd
    for i, d in enumerate(sd.query_devices()):
        if d['max_input_channels'] > 0 and 'Pilote de capture' in d.get('name', ''):
            return i
    return None


async def record_with_silence_detection(silence_duration: float = 2.0, max_duration: float = 30.0) -> bytes:
    """Record mic with auto-calibrated silence detection.

    1. Measures ambient noise for 0.5s to set threshold dynamically
    2. Waits for speech (above threshold)
    3. Stops after silence_duration seconds of silence post-speech
    """
    import sounddevice as sd
    import numpy as np

    sample_rate = 16000
    input_device = _find_mic_device()

    # --- Step 1: Calibrate ambient noise (0.5s) ---
    calibration = sd.rec(int(0.5 * sample_rate), samplerate=sample_rate,
                         channels=1, dtype="int16", device=input_device)
    sd.wait()
    ambient_rms = np.sqrt(np.mean(calibration.astype(np.float32) ** 2)) / 32768.0
    # Threshold = 3x ambient noise (speech is typically 5-20x louder than ambient)
    threshold = max(ambient_rms * 3.0, 0.005)

    # --- Step 2: Record with silence detection ---
    recording_chunks: list[bytes] = []
    silence_start: float | None = None
    has_speech = False
    stop = asyncio.Event()

    def audio_callback(indata, frames, time_info, status):
        nonlocal silence_start, has_speech
        recording_chunks.append(indata.copy().tobytes())

        rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2)) / 32768.0
        if rms > threshold:
            has_speech = True
            silence_start = None
        elif has_speech:
            if silence_start is None:
                silence_start = time.time()
            elif time.time() - silence_start > silence_duration:
                stop.set()

    stream = sd.InputStream(
        samplerate=sample_rate, channels=1, dtype="int16",
        callback=audio_callback, blocksize=4096,
        device=input_device,
    )
    stream.start()

    try:
        await asyncio.wait_for(stop.wait(), timeout=max_duration)
    except (asyncio.TimeoutError, asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        stream.stop()
        stream.close()

    return b"".join(recording_chunks) if recording_chunks else b""


async def transcribe_audio(audio_bytes: bytes, sample_rate: int = 16000) -> str:
    """Transcribe audio using Deepgram REST API (much more reliable than WebSocket for pre-recorded)."""
    import httpx

    api_key = os.getenv("DEEPGRAM_API_KEY", "")
    if not api_key:
        return ""

    url = "https://api.deepgram.com/v1/listen"
    params = {
        "language": "en",
        "model": "nova-2",
        "punctuate": "true",
        "sample_rate": str(sample_rate),
        "encoding": "linear16",
        "channels": "1",
    }

    async def _do_request():
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                params=params,
                headers={
                    "Authorization": f"Token {api_key}",
                    "Content-Type": "audio/raw",
                },
                content=audio_bytes,
            )
            response.raise_for_status()
            return response.json()

    # Shield from cancellation (Ctrl+C during transcription)
    data = await asyncio.shield(_do_request())

    # Extract transcript
    channels = data.get("results", {}).get("channels", [])
    if channels:
        alternatives = channels[0].get("alternatives", [])
        if alternatives:
            return alternatives[0].get("transcript", "")
    return ""


async def voice_call(char_name: str, agent, orchestrator, session, quest, renderer=None):
    """Streaming voice conversation — pipes Claude output directly into TTS playback.

    Flow per turn:
        1. Record mic with silence detection
        2. Transcribe via Deepgram REST
        3. Stream Claude → buffer sentences → TTS each sentence → play immediately
        4. Repeat until silence / Ctrl+C
    """
    import sounddevice as sd
    import numpy as np
    import io

    color = char_color_map.get(char_name, Fore.WHITE)
    voice_id = agent.character.voice_id
    has_tts = (
        voice_id
        and voice_id != "elevenlabs_placeholder"
        and os.getenv("ELEVENLABS_API_KEY")
    )

    print(f"\n{color}{'━' * 60}")
    print(f"  Calling {char_name}...")
    print(f"  (speak naturally — auto-detects when you stop)")
    print(f"  (press Enter to hang up)")
    print(f"{'━' * 60}{RESET}\n")

    # Hangup listener — sets event when Enter is pressed
    hangup = asyncio.Event()
    async def _hangup_listener():
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, input)
        hangup.set()
    hangup_task = asyncio.create_task(_hangup_listener())

    tts = None
    if has_tts:
        from agents.voice.tts import ElevenLabsTTS
        tts = ElevenLabsTTS(voice_id=voice_id)

    turn = 0
    while True:
        turn += 1

        # Check if player hung up
        if hangup.is_set():
            break

        # --- Record with silence detection ---
        print(f"{Fore.GREEN}  Listening...{RESET}", flush=True)
        try:
            audio = await record_with_silence_detection()
        except Exception as e:
            sys_print(f"Recording error: {e}")
            break

        if hangup.is_set():
            break

        if not audio or len(audio) < 16000:
            if turn > 1:
                sys_print("Call ended.")
            else:
                sys_print("No speech detected. Call ended.")
            break

        duration = len(audio) / (16000 * 2)
        sys_print(f"Transcribing {duration:.1f}s...")

        # --- Transcribe ---
        transcript = await transcribe_audio(audio)
        if not transcript.strip():
            sys_print("Couldn't catch that. Say again or stay silent to hang up.")
            continue

        cprint(Fore.GREEN, "you", transcript)

        # --- Stream Claude → sentence buffer → TTS → play (pipelined) ---
        print(f"\n{color}{'━' * 60}")
        print(f"  {char_name}")
        print(f"{'━' * 60}{RESET}")

        full_reply = ""
        sentence_buffer = ""
        sentence_enders = {".", "!", "?"}
        audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

        async def tts_producer():
            """Stream Claude chunks, flush complete sentences to TTS, queue audio."""
            nonlocal full_reply, sentence_buffer
            try:
                async for chunk in agent.respond_stream(transcript):
                    print(chunk, end="", flush=True)
                    full_reply += chunk
                    sentence_buffer += chunk

                    # Flush on sentence boundaries
                    while sentence_buffer:
                        earliest = -1
                        for ender in sentence_enders:
                            pos = sentence_buffer.find(ender)
                            if pos != -1 and (earliest == -1 or pos < earliest):
                                earliest = pos
                        if earliest == -1:
                            break
                        sentence = sentence_buffer[: earliest + 1].strip()
                        sentence_buffer = sentence_buffer[earliest + 1 :]
                        if sentence and tts:
                            try:
                                audio_bytes = await tts.synthesize(sentence)
                                await audio_queue.put(audio_bytes)
                            except Exception:
                                pass

                # Flush remaining
                if sentence_buffer.strip() and tts:
                    try:
                        audio_bytes = await tts.synthesize(sentence_buffer.strip())
                        await audio_queue.put(audio_bytes)
                    except Exception:
                        pass
            finally:
                await audio_queue.put(None)

        async def audio_player():
            """Play MP3 audio chunks as they arrive."""
            try:
                from pydub import AudioSegment
                while True:
                    mp3_data = await audio_queue.get()
                    if mp3_data is None:
                        break
                    try:
                        segment = AudioSegment.from_mp3(io.BytesIO(mp3_data))
                        samples = np.array(segment.get_array_of_samples(), dtype="int16")
                        if segment.channels == 2:
                            samples = samples.reshape((-1, 2))
                        sd.play(samples, samplerate=segment.frame_rate)
                        sd.wait()
                    except Exception:
                        pass
            except ImportError:
                # No pydub — drain queue, text still shows
                while True:
                    if await audio_queue.get() is None:
                        break

        # Run producer (Claude→TTS) and player concurrently
        # Audio plays as soon as the first sentence is synthesized
        producer_task = asyncio.create_task(tts_producer())
        player_task = asyncio.create_task(audio_player())
        await producer_task
        await player_task

        print(f"\n{color}{'━' * 60}{RESET}\n")

        # --- Orchestrator (true fire-and-forget — doesn't block next turn) ---
        async def _orchestrator_bg():
            try:
                action = PlayerAction(type="voice", content=transcript, target_character=char_name)
                events = await orchestrator.react("player_message", action)
                for event in events:
                    await event_print(event, renderer, quest)
            except Exception:
                pass
        asyncio.create_task(_orchestrator_bg())

    hangup_task.cancel()
    print(f"{color}  Call with {char_name} ended.{RESET}\n")


# --- Camera / AI Vision ---

async def interpret_photo(description: str, quest: QuestOutput, step_idx: int):
    """AI interprets a photo description in the quest narrative context."""
    from anthropic import AsyncAnthropic

    step = quest.steps[step_idx] if step_idx < len(quest.steps) else None
    camera_context = step.camera_prompt if step else ""
    step_title = step.title if step else "unknown"

    client = AsyncAnthropic(
        base_url=os.getenv("ANTHROPIC_BASE_URL"),
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
    )

    prompt = f"""You are an AI vision system integrated into an immersive quest called "{quest.title}".
The player just photographed something and described it as: "{description}"

Current step: {step_title}
Camera context from the quest designer: {camera_context}

Interpret what the player sees through the lens of the quest narrative. Be vivid,
specific, and tie what they see to the story. 3-5 sentences max. Stay in the quest's
tone ({quest.tone}). Reference real architectural/visual details from the description."""

    response = await client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text if response.content else ""
    cprint(CAM_COLOR, "AI Vision", text)
    return text


# --- Find character by partial name ---

def find_character(quest: QuestOutput, name_query: str) -> tuple[str, CharacterAgent | None]:
    """Find a character by partial name match."""
    query = name_query.strip().lower()
    for char in quest.characters:
        if query in char.name.lower():
            return char.name, None  # Agent will be fetched from orchestrator
    return "", None


# --- Main ---

async def main():
    # Load quest
    quest_file = "quest_highstakes.json"
    if not os.path.exists(quest_file):
        print(f"Error: {quest_file} not found. Run run_generate.py first.")
        return

    with open(quest_file, "r", encoding="utf-8") as f:
        quest_data = json.load(f)
    quest = QuestOutput(**quest_data)

    print(f"\n{Fore.CYAN + Style.BRIGHT}{'=' * 60}")
    print(f"  QUEST SIMULATION: {quest.title}")
    print(f"  Tone: {quest.tone} | Steps: {len(quest.steps)} | Characters: {len(quest.characters)}")
    print(f"{'=' * 60}{RESET}\n")

    # Assign colors to characters
    for i, char in enumerate(quest.characters):
        char_color_map[char.name] = CHAR_COLORS[i % len(CHAR_COLORS)]
        print(f"  {CHAR_COLORS[i % len(CHAR_COLORS)]}{char.name}{RESET} ({char.archetype or char.type})")
    print()

    # Create session
    session = QuestSession(
        quest_id=quest.quest_id,
        state=SessionState(
            current_step=1,
            characters_trust=[
                CharacterTrust(character_name=c.name, trust_level=50)
                for c in quest.characters
            ],
        ),
    )

    # Create orchestrator
    def debug_cb(type_, data):
        if type_ == "reasoning":
            cprint(Style.DIM, "orchestrator", data[:200])
        elif type_ == "tool_call":
            cprint(Style.DIM, f"orch:{data['name']}", str(data['input'])[:150])

    orchestrator = OrchestratorAgent(quest, session, debug_callback=debug_cb)
    renderer = ArtifactRenderer("artifacts")
    start_time = time.time()

    # --- Opening — first contact (intriguing call) ---
    sys_print("Starting quest... incoming call")
    try:
        events = await orchestrator.react("start")
        for event in events:
            await event_print(event, renderer, quest)
    except Exception as e:
        sys_print(f"Orchestrator start error: {e}")

    # --- After first contact: briefing + bundle drop into vault ---
    sys_print("New documents in your vault...")
    try:
        # Briefing (hook + situation + your role)
        briefing_path = renderer.render_briefing_pdf(quest)
        cprint(GPS_COLOR, "vault:briefing", briefing_path)
        try:
            os.startfile(briefing_path)
        except Exception:
            pass

        # Rest of pre-quest bundle (email, voicemail, classified doc, playlist)
        bundle_files = await renderer.render_pre_quest_bundle(quest)
        for name, path in bundle_files.items():
            cprint(GPS_COLOR, f"vault:{name}", path)
            try:
                os.startfile(path)
            except Exception:
                pass
    except Exception as e:
        sys_print(f"Vault generation error: {e}")

    # --- Print available commands ---
    print(f"{SYS_COLOR}Commands: @Name: msg | /voice Name | /goto step N | /photo desc | /rayban desc | /next | /status | /chars | /quit{RESET}\n")

    # --- Main loop ---
    loop = asyncio.get_event_loop()

    while True:
        try:
            raw = await loop.run_in_executor(None, lambda: input(f"{Fore.WHITE + Style.BRIGHT}> {RESET}"))
        except (EOFError, KeyboardInterrupt):
            break

        raw = raw.strip()
        if not raw:
            continue

        # Update elapsed time
        session.state.total_elapsed_seconds = int(time.time() - start_time)

        # --- /quit ---
        if raw.lower() in ("/quit", "/exit", "/q"):
            sys_print("Quest ended.")
            break

        # --- /status ---
        elif raw.lower() == "/status":
            step = quest.steps[session.state.current_step - 1] if session.state.current_step <= len(quest.steps) else None
            print(f"\n{GPS_COLOR}{'─' * 50}")
            print(f"  Step: {session.state.current_step}/{len(quest.steps)} — {step.title if step else '?'}")
            print(f"  Location: {step.activity.name if step else '?'}")
            print(f"  Elapsed: {session.state.total_elapsed_seconds // 60}min")
            print(f"  Beats completed: {session.state.beats_completed}")
            for ct in session.state.characters_trust:
                color = char_color_map.get(ct.character_name, "")
                print(f"  {color}{ct.character_name}{RESET}: trust {ct.trust_level}/100")
            print(f"{'─' * 50}{RESET}\n")

        # --- /chars ---
        elif raw.lower() == "/chars":
            for char in quest.characters:
                color = char_color_map.get(char.name, "")
                print(f"  {color}{char.name}{RESET} — {char.archetype} — {char.relationship_to_player[:80]}")
            print()

        # --- /next ---
        elif raw.lower() == "/next":
            if session.state.current_step < len(quest.steps):
                session.state.current_step += 1
                step = quest.steps[session.state.current_step - 1]
                print(f"\n{GPS_COLOR}{'═' * 60}")
                print(f"  STEP {step.step_id}: {step.title}")
                print(f"  {step.activity.name} — {step.activity.address}")
                print(f"  Walking: {step.walking_minutes_from_previous} min from previous")
                print(f"{'═' * 60}{RESET}")
                print(f"\n{step.narrative_intro}\n")
                if step.instruction:
                    cprint(Fore.WHITE + Style.BRIGHT, "instruction", step.instruction)
                if step.player_action:
                    cprint(Fore.GREEN, "action", step.player_action)
                print()
            else:
                sys_print("Already at the last step!")

        # --- /goto step N ---
        elif raw.lower().startswith("/goto"):
            parts = raw.split()
            try:
                # /goto step 3 or /goto 3
                step_num = int(parts[-1])
                if 1 <= step_num <= len(quest.steps):
                    session.state.current_step = step_num
                    step = quest.steps[step_num - 1]

                    print(f"\n{GPS_COLOR}{'═' * 60}")
                    print(f"  ARRIVING AT STEP {step.step_id}: {step.title}")
                    print(f"  {step.activity.name} — {step.activity.address}")
                    print(f"{'═' * 60}{RESET}")
                    print(f"\n{step.narrative_intro}\n")

                    if step.instruction:
                        cprint(Fore.WHITE + Style.BRIGHT, "instruction", step.instruction)
                    if step.player_action:
                        cprint(Fore.GREEN, "action", step.player_action)

                    # GPS trigger
                    if step.gps_trigger:
                        trigger = step.gps_trigger
                        char_name = trigger.get("character", "System")
                        content = trigger.get("content_brief", "")
                        ttype = trigger.get("type", "message")
                        print()
                        cprint(GPS_COLOR, f"GPS unlock ({ttype})", f"[{char_name}] {content}")

                    # Unlock message
                    if step.unlock_message:
                        print()
                        cprint(GPS_COLOR, "unlock", step.unlock_message)

                    # Trigger orchestrator
                    try:
                        action = PlayerAction(type="move", content=f"Arrived at step {step_num}")
                        events = await orchestrator.react("gps_arrival", action)
                        for event in events:
                            await event_print(event, renderer, quest)
                    except Exception as e:
                        sys_print(f"Orchestrator error: {e}")

                    print()
                else:
                    sys_print(f"Step must be 1-{len(quest.steps)}")
            except (ValueError, IndexError):
                sys_print("Usage: /goto step 3  or  /goto 3")

        # --- /gps lat lon ---
        elif raw.lower().startswith("/gps"):
            parts = raw.split()
            if len(parts) >= 3:
                try:
                    lat, lon = float(parts[1]), float(parts[2])
                    cprint(GPS_COLOR, "GPS", f"Position updated: {lat}, {lon}")
                    action = PlayerAction(type="move", content=f"GPS: {lat}, {lon}", gps_coords=[lat, lon])
                    events = await orchestrator.react("heartbeat", action)
                    for event in events:
                        await event_print(event, renderer, quest)
                except ValueError:
                    sys_print("Usage: /gps 43.5528 7.0174")
            else:
                sys_print("Usage: /gps 43.5528 7.0174")

        # --- /photo or /rayban ---
        elif raw.lower().startswith("/photo") or raw.lower().startswith("/rayban"):
            description = raw.split(maxsplit=1)[1] if len(raw.split(maxsplit=1)) > 1 else ""
            if not description:
                sys_print("Usage: /photo I see an old stone facade with a coat of arms")
                continue
            device = "Ray-Ban Meta" if raw.lower().startswith("/rayban") else "phone camera"
            cprint(CAM_COLOR, device, f"Analyzing: {description}")
            try:
                await interpret_photo(description, quest, session.state.current_step - 1)
                async def _photo_bg(dev=device, desc=description):
                    try:
                        action = PlayerAction(type="custom", content=f"[{dev} photo] {desc}")
                        events = await orchestrator.react("player_message", action)
                        for event in events:
                            await event_print(event, renderer, quest)
                    except Exception:
                        pass
                asyncio.create_task(_photo_bg())
            except Exception as e:
                sys_print(f"Vision error: {e}")

        # --- /voice CharName ---
        elif raw.lower().startswith("/voice"):
            name_query = raw[6:].strip()
            if not name_query:
                sys_print("Usage: /voice Lena Voss")
                continue

            char_name, _ = find_character(quest, name_query)
            if not char_name:
                sys_print(f"Character not found: {name_query}")
                continue

            agent = orchestrator.get_character_agent(char_name)
            if not agent:
                sys_print(f"No agent for {char_name}")
                continue

            try:
                await voice_call(char_name, agent, orchestrator, session, quest, renderer)
            except KeyboardInterrupt:
                print(f"\n{char_color_map.get(char_name, '')}  Call ended.{RESET}\n")

        # --- @CharName: message ---
        elif raw.startswith("@"):
            # Parse @CharName: message
            if ":" not in raw:
                sys_print("Usage: @Lena Voss: your message here")
                continue

            name_part, message = raw[1:].split(":", 1)
            message = message.strip()
            if not message:
                sys_print("Empty message")
                continue

            char_name, _ = find_character(quest, name_part)
            if not char_name:
                sys_print(f"Character not found: {name_part}")
                continue

            agent = orchestrator.get_character_agent(char_name)
            if not agent:
                sys_print(f"No agent for {char_name}")
                continue

            # Get response (text only — no TTS for text messages)
            sys_print(f"Waiting for {char_name}...")
            event = await agent.respond(message)
            char_print(char_name, event.content)

            # Orchestrator follow-up (non-blocking)
            async def _msg_bg(msg=message, cn=char_name):
                try:
                    action = PlayerAction(type="message", content=msg, target_character=cn)
                    events = await orchestrator.react("player_message", action)
                    for event in events:
                        await event_print(event, renderer, quest)
                except Exception:
                    pass
            asyncio.create_task(_msg_bg())

        else:
            sys_print("Unknown command. Try: @Name: msg | /voice Name | /goto step N | /photo desc | /next | /status | /quit")


if __name__ == "__main__":
    asyncio.run(main())

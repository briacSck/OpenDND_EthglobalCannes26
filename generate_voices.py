"""One-shot script to generate ElevenLabs voices for all characters in checkpoints."""

import asyncio
import json
import glob
import os

from dotenv import load_dotenv
load_dotenv()

from agents.voice.tts import ElevenLabsTTS


async def main():
    files = sorted(glob.glob("checkpoints/character_*.json"))
    print(f"Found {len(files)} characters\n")

    for f in files:
        with open(f, encoding="utf-8") as fh:
            char = json.load(fh)

        name = char["name"]
        current_voice = char.get("voice_id", "")

        # Skip if already has a real voice_id (not a placeholder)
        if current_voice and current_voice != "elevenlabs_placeholder" and not any(
            kw in current_voice for kw in ["male", "female", "whisper", "androgynous", "authoritative", "sultry"]
        ):
            print(f"[SKIP] {name} — already has voice_id: {current_voice}")
            continue

        # Build description from character traits
        personality = char.get("personality", "")[:200]
        speech = char.get("speech_pattern", "")[:150]
        archetype = char.get("archetype", "")
        voice_hint = current_voice if current_voice != "elevenlabs_placeholder" else ""

        # Sanitize text — remove non-ASCII chars that break Windows console + API
        description = f"{name}. {personality}. Speech style: {speech}."
        if voice_hint:
            description += f" Voice type: {voice_hint}."
        if archetype:
            description += f" Archetype: {archetype}."
        description = description.encode("ascii", errors="ignore").decode("ascii")

        print(f"[GENERATING] {name}...")
        print(f"  Description: {description[:120]}...")

        try:
            voice_id = await ElevenLabsTTS.generate_voice(description)
            char["voice_id"] = voice_id
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(char, fh, ensure_ascii=False, indent=2)
            print(f"  [OK] {name} -> {voice_id}\n")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}\n")

        # Rate limit: wait between API calls
        await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())

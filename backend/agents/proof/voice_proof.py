"""Voice proof — transcribe audio via Whisper and match against verification target."""

from __future__ import annotations

import base64
import logging
import struct
import tempfile
from pathlib import Path

from agents.proof.models import ProofResult
from agents.quest_generation.models import Verification
from config import DEMO_MODE, OPENAI_API_KEY

logger = logging.getLogger(__name__)

_EXT_MAP = {
    "pcm_16khz": ".wav",
    "aac": ".aac",
    "opus": ".opus",
}


def _wrap_pcm_as_wav(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, bits: int = 16) -> bytes:
    """Wrap raw PCM bytes in a WAV header (16-bit LE mono 16kHz)."""
    byte_rate = sample_rate * channels * (bits // 8)
    block_align = channels * (bits // 8)
    data_size = len(pcm_data)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,             # chunk size
        1,              # PCM format
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits,
        b"data",
        data_size,
    )
    return header + pcm_data


async def verify_voice(
    audio_b64: str,
    encoding: str,
    duration_ms: int,
    verification: Verification,
) -> ProofResult:
    """Transcribe audio and check if transcript matches the verification target.

    In DEMO_MODE: returns a mock verified result instantly.
    """
    if DEMO_MODE:
        return ProofResult(
            verified=True,
            confidence=0.95,
            transcript=f"Demo transcript: {verification.target}",
            matched_keyword=verification.target,
        )

    if not OPENAI_API_KEY:
        return ProofResult(
            verified=False,
            description="OPENAI_API_KEY not configured for voice transcription",
        )

    import openai

    raw_bytes = base64.b64decode(audio_b64)

    # PCM needs a WAV wrapper for Whisper
    if encoding == "pcm_16khz":
        raw_bytes = _wrap_pcm_as_wav(raw_bytes)

    ext = _EXT_MAP.get(encoding, ".wav")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(raw_bytes)
        tmp_path = Path(tmp.name)

    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        with open(tmp_path, "rb") as audio_file:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
        transcript = result.text.strip()
    finally:
        tmp_path.unlink(missing_ok=True)

    logger.info("Whisper transcript: %s", transcript[:200])

    # Match against verification target (case-insensitive substring)
    target = (verification.target or "").lower()
    condition = (verification.success_condition or "").lower()
    transcript_lower = transcript.lower()

    matched = False
    matched_keyword = None

    if target and target in transcript_lower:
        matched = True
        matched_keyword = verification.target
    elif condition and condition in transcript_lower:
        matched = True
        matched_keyword = verification.success_condition

    return ProofResult(
        verified=matched,
        confidence=0.85 if matched else 0.2,
        transcript=transcript,
        matched_keyword=matched_keyword,
    )

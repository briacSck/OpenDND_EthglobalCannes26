"""Image proof — verify images via Anthropic vision, extract frames from video."""

from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
from pathlib import Path

import anthropic

from agents.proof.models import ProofResult
from agents.quest_generation.models import Verification
from config import ANTHROPIC_API_KEY, DEMO_MODE

logger = logging.getLogger(__name__)


async def extract_frame_from_video(video_b64: str) -> tuple[str, str]:
    """Extract the first frame from a base64-encoded MP4 video.

    Returns (frame_b64, media_type).
    Requires ffmpeg to be installed on the system.
    """
    raw_bytes = base64.b64decode(video_b64)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_in:
        tmp_in.write(raw_bytes)
        input_path = Path(tmp_in.name)

    output_path = input_path.with_suffix(".jpg")

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", str(input_path),
            "-vframes", "1", "-f", "image2",
            str(output_path),
            "-y",  # overwrite
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {stderr.decode()[:300]}")

        if not output_path.exists():
            raise RuntimeError("ffmpeg produced no output frame")

        frame_bytes = output_path.read_bytes()
        frame_b64 = base64.b64encode(frame_bytes).decode()
        return frame_b64, "image/jpeg"

    except FileNotFoundError:
        raise RuntimeError("ffmpeg not available for video processing")
    finally:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


async def verify_image(
    frame_b64: str,
    media_type: str,
    verification: Verification,
) -> ProofResult:
    """Verify an image against a verification condition using Anthropic vision.

    Calls Anthropic directly (not compute_client) because compute_client
    does not support multimodal content blocks.

    In DEMO_MODE: returns a mock verified result instantly.
    """
    if DEMO_MODE:
        return ProofResult(
            verified=True,
            confidence=0.92,
            description=f"Demo: verified — {verification.success_condition}",
        )

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    response = await client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": frame_b64,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        f"Does this image show: {verification.success_condition}? "
                        "Answer YES or NO on the first line, then explain briefly."
                    ),
                },
            ],
        }],
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text

    lines = text.strip().split("\n", 1)
    first_line = lines[0].strip().upper()
    description = lines[1].strip() if len(lines) > 1 else text.strip()

    verified = first_line.startswith("YES")
    confidence = 0.85 if verified else 0.15

    logger.info("Image proof: verified=%s, desc=%s", verified, description[:100])

    return ProofResult(
        verified=verified,
        confidence=confidence,
        description=description,
    )

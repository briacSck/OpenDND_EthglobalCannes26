"""Proof verification — voice transcription, image recognition, video frame extraction."""

from agents.proof.image_proof import extract_frame_from_video, verify_image
from agents.proof.models import ProofResult
from agents.proof.voice_proof import verify_voice

__all__ = [
    "ProofResult",
    "extract_frame_from_video",
    "verify_image",
    "verify_voice",
]

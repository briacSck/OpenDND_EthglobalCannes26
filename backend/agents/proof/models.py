"""Proof models — structured results from voice and image verification."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProofResult(BaseModel):
    """Outcome of a proof verification attempt."""

    verified: bool
    confidence: float = Field(default=0.0, description="0.0-1.0 confidence score")
    transcript: str | None = Field(default=None, description="Voice proof: Whisper transcript")
    matched_keyword: str | None = Field(default=None, description="Voice proof: keyword that matched")
    description: str | None = Field(default=None, description="Image proof: what the image shows")
    step_id: int | None = Field(default=None, description="Step this proof was submitted for")

"""
WhisperNet Backend — Response Schemas

Pydantic models for all outgoing API payloads.
"""

from pydantic import BaseModel, Field


class VoiceSettings(BaseModel):
    """Voice configuration directives for OpenAI Realtime API."""

    voice_id: str = Field(
        default="alloy",
        description="OpenAI Realtime voice ID (alloy, echo, shimmer, etc.).",
    )
    speed: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Speech speed multiplier.",
    )
    emotional_tone: str = Field(
        default="neutral",
        description="Emotional tone directive derived from the current scene context.",
    )


class GeneratePromptResponse(BaseModel):
    """
    Output payload sent to OpenAI Realtime / Member 4's pipeline.
    Contains the fully synthesized persona prompt and voice settings.
    """

    system_instructions: str = Field(
        ...,
        description="The fully synthesized persona prompt with lore, context, and guardrails.",
    )
    voice_settings: VoiceSettings = Field(
        default_factory=VoiceSettings,
        description="Voice configuration for the AI response.",
    )
    user_input: str = Field(
        ...,
        description="The sanitized user question.",
    )
    active_character: str = Field(
        default="Narrator",
        description="The character persona the AI will adopt.",
    )


class RealtimeTokenResponse(BaseModel):
    """Response from the ephemeral token / SDP exchange endpoint."""

    sdp_answer: str = Field(
        ...,
        description="The remote SDP answer from OpenAI for WebRTC connection.",
    )
    session_id: str = Field(
        ...,
        description="The ephemeral session identifier.",
    )


class SessionResponse(BaseModel):
    """Response from session management endpoints."""

    session_id: str = Field(
        ...,
        description="Unique session identifier.",
    )
    created_at: float = Field(
        ...,
        description="Unix timestamp of session creation.",
    )
    last_active: float = Field(
        ...,
        description="Unix timestamp of last session activity.",
    )
    episode_index: int = Field(
        ...,
        description="Current episode the user is on.",
    )
    timestamp: float = Field(
        ...,
        description="Current playback timestamp within the episode.",
    )
    rolling_context_length: int = Field(
        default=0,
        description="Length of the stored rolling context in characters.",
    )
    is_active: bool = Field(
        default=True,
        description="Whether the session is currently active.",
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="healthy")
    timestamp: str = Field(..., description="ISO 8601 timestamp.")
    version: str = Field(..., description="Application version.")
    environment: str = Field(default="development")


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    error: str = Field(..., description="Error type identifier.")
    detail: str = Field(..., description="Human-readable error description.")

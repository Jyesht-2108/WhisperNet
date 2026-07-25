"""
WhisperNet Backend — Request Schemas

Pydantic models for all incoming API payloads,
matching the data contracts defined in the PRD.
"""

from pydantic import BaseModel, Field


class PlaybackState(BaseModel):
    """Current playback position for spoiler boundary enforcement."""

    episode_index: int = Field(
        ...,
        ge=1,
        description="The current episode number the user is listening to. "
        "Used as the hard ceiling for spoiler prevention.",
    )
    timestamp: float = Field(
        default=0.0,
        ge=0.0,
        description="Current playback timestamp in seconds within the episode.",
    )


class GeneratePromptRequest(BaseModel):
    """
    Payload received from the Chrome Extension (via Member 1 / Member 4)
    when the user interrupts the story to ask a question.
    """

    user_query: str = Field(
        default="",
        max_length=2000,
        description="The live transcribed text of what the user just asked.",
    )
    rolling_context: str = Field(
        ...,
        max_length=10000,
        description="The last ~60-90 seconds of transcribed story audio (rolling buffer).",
    )
    playback_state: PlaybackState = Field(
        ...,
        description="Current playback state containing episode index and timestamp.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_query": "Who is the giant statue in the dungeon?",
                    "rolling_context": (
                        "The statues began to move, their eyes glowing red. "
                        "Jin-Woo felt his legs tremble as the massive stone figure "
                        "turned its head toward the remaining hunters. The Statue of God "
                        "raised its hand, and a blinding light filled the chamber."
                    ),
                    "playback_state": {"episode_index": 3, "timestamp": 142.5},
                }
            ]
        }
    }


class SessionCreateRequest(BaseModel):
    """Payload for initializing a new client session."""

    episode_index: int = Field(
        default=1,
        ge=1,
        description="Initial episode number the user is listening to.",
    )
    timestamp: float = Field(
        default=0.0,
        ge=0.0,
        description="Initial playback timestamp in seconds.",
    )


class SessionUpdatePayload(BaseModel):
    """Payload for updating an existing session's state."""

    episode_index: int | None = Field(
        default=None,
        ge=1,
        description="Updated episode number.",
    )
    timestamp: float | None = Field(
        default=None,
        ge=0.0,
        description="Updated playback timestamp in seconds.",
    )
    rolling_context: str | None = Field(
        default=None,
        max_length=20000,
        description="Updated rolling transcript context.",
    )


class WebSocketMessage(BaseModel):
    """
    Structured message for WebSocket communication.
    The 'type' field determines how the backend processes the payload.
    """

    type: str = Field(
        ...,
        description=(
            "Message type. Supported: 'context_update', 'ask_question', 'ping'."
        ),
    )
    user_query: str | None = Field(
        default=None,
        max_length=2000,
        description="The user's question (required for 'ask_question' type).",
    )
    rolling_context: str | None = Field(
        default=None,
        max_length=20000,
        description="Updated rolling transcript (for 'context_update' type).",
    )
    episode_index: int | None = Field(
        default=None,
        ge=1,
        description="Current episode index.",
    )
    timestamp: float | None = Field(
        default=None,
        ge=0.0,
        description="Current playback timestamp.",
    )


class RealtimeTokenRequest(BaseModel):
    """
    Payload for OpenAI Realtime API ephemeral token / SDP exchange.
    The client sends its SDP offer, and the backend negotiates with
    OpenAI using the master API key, returning the SDP answer.
    """

    sdp_offer: str = Field(
        ...,
        min_length=1,
        description="The local WebRTC Session Description Protocol (SDP) offer.",
    )
    model: str = Field(
        default="gpt-4o-realtime-preview-2024-12-17",
        description="The OpenAI Realtime model to use.",
    )

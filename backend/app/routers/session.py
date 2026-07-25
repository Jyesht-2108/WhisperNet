"""
WhisperNet Backend — Session Management Router

REST endpoints for creating, reading, updating, and deleting
client sessions. Each session tracks the user's playback state
(episode index, timestamp) and rolling context buffer.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.models.requests import SessionCreateRequest, SessionUpdatePayload
from app.models.responses import ErrorResponse, SessionResponse
from app.services.session_manager import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/session", tags=["Session Management"])

# Shared session manager instance (started in app lifespan)
session_manager = SessionManager()


@router.post(
    "",
    response_model=SessionResponse,
    status_code=201,
    responses={
        500: {"model": ErrorResponse, "description": "Internal error"},
    },
    summary="Create a new client session",
    description=(
        "Initialize a new session for a Chrome Extension client. Returns a "
        "unique session_id that should be used for all subsequent state syncs "
        "and WebSocket connections."
    ),
)
async def create_session(request: SessionCreateRequest) -> SessionResponse:
    """Create a new session and return the session state."""
    session = session_manager.create_session(
        episode_index=request.episode_index,
        timestamp=request.timestamp,
    )
    return SessionResponse(**session.to_dict())


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
    summary="Get session state",
    description="Retrieve the current state of an existing session.",
)
async def get_session(session_id: str) -> SessionResponse:
    """Retrieve a session by its ID."""
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found or expired.",
        )
    return SessionResponse(**session.to_dict())


@router.patch(
    "/{session_id}",
    response_model=SessionResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
    summary="Update session state",
    description=(
        "Partially update a session's playback state. Only provided fields "
        "are changed; omitted fields remain unchanged."
    ),
)
async def update_session(
    session_id: str,
    payload: SessionUpdatePayload,
) -> SessionResponse:
    """Update fields on an existing session."""
    session = session_manager.update_session(
        session_id=session_id,
        episode_index=payload.episode_index,
        timestamp=payload.timestamp,
        rolling_context=payload.rolling_context,
    )
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found or expired.",
        )
    return SessionResponse(**session.to_dict())


@router.delete(
    "/{session_id}",
    status_code=204,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
    summary="Delete a session",
    description="Destroy a session and free associated resources.",
)
async def delete_session(session_id: str) -> None:
    """Delete a session by its ID."""
    deleted = session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )

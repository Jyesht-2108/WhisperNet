"""
WhisperNet Backend — OpenAI Realtime Token Exchange Router

Handles ephemeral token / SDP exchange for secure WebRTC connections.
The Chrome Extension cannot store the OpenAI API key (easily decompiled),
so this endpoint acts as a secure intermediary — receiving the client's
SDP offer, negotiating with OpenAI using the master key, and returning
the SDP answer for the WebRTC PeerConnection.
"""

import logging

import httpx
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.requests import RealtimeTokenRequest
from app.models.responses import ErrorResponse, RealtimeTokenResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/realtime", tags=["OpenAI Realtime"])

# OpenAI Realtime session endpoint
OPENAI_REALTIME_SESSION_URL = "https://api.openai.com/v1/realtime/client_secrets"


@router.post(
    "/token",
    response_model=RealtimeTokenResponse,
    responses={
        502: {"model": ErrorResponse, "description": "OpenAI API error"},
        500: {"model": ErrorResponse, "description": "Internal error"},
    },
    summary="Exchange SDP offer for ephemeral token",
    description=(
        "Receives the client's WebRTC SDP offer, negotiates with OpenAI's "
        "Realtime API using the server's master API key, and returns the "
        "SDP answer containing an ephemeral session token. This ensures "
        "the API key never leaves the backend."
    ),
)
async def exchange_token(request: RealtimeTokenRequest) -> RealtimeTokenResponse:
    """
    Ephemeral token exchange flow:
    1. Receive SDP offer from the Chrome Extension client
    2. Forward to OpenAI Realtime API with master API key
    3. Return the SDP answer (with ephemeral session) to the client
    """
    settings = get_settings()

    if settings.OPENAI_API_KEY == "sk-placeholder":
        raise HTTPException(
            status_code=500,
            detail="OpenAI API key is not configured. Update OPENAI_API_KEY in .env",
        )

    logger.info("Ephemeral token exchange requested for model: %s", request.model)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Step 1: Create an ephemeral session
            session_response = await client.post(
                OPENAI_REALTIME_SESSION_URL,
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "session": {
                        "model": request.model,
                        "type": "realtime",
                    }
                },
            )
            session_response.raise_for_status()
            session_data = session_response.json()

            ephemeral_key = session_data.get("value") or session_data.get("client_secret", {}).get("value")
            session_id = session_data.get("session", {}).get("id", "unknown")

            if not ephemeral_key:
                logger.error("No ephemeral key in OpenAI response: %s", session_data)
                raise HTTPException(
                    status_code=502,
                    detail="OpenAI did not return an ephemeral key.",
                )

            # Step 2: Use ephemeral key to negotiate WebRTC SDP
            sdp_response = await client.post(
                f"https://api.openai.com/v1/realtime?model={request.model}",
                headers={
                    "Authorization": f"Bearer {ephemeral_key}",
                    "Content-Type": "application/sdp",
                },
                content=request.sdp_offer,
            )
            sdp_response.raise_for_status()

            sdp_answer = sdp_response.text

            logger.info(
                "Ephemeral token exchange successful: session_id=%s",
                session_id,
            )

            return RealtimeTokenResponse(
                sdp_answer=sdp_answer,
                session_id=session_id,
            )

    except httpx.HTTPStatusError as e:
        logger.error(
            "OpenAI API error (%d): %s",
            e.response.status_code,
            e.response.text[:500],
        )
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI API returned {e.response.status_code}: {e.response.text[:200]}",
        ) from e
    except httpx.RequestError as e:
        logger.error("OpenAI API connection error: %s", str(e))
        raise HTTPException(
            status_code=502,
            detail="Failed to connect to OpenAI API.",
        ) from e

"""
WhisperNet Backend — WebSocket Handler

Bi-directional WebSocket endpoint for real-time communication between
the Chrome Extension (Member 1 / Member 4) and the backend. Handles
three message types:
  - 'context_update': Extension pushes rolling transcript + playback state
  - 'ask_question':   User interrupts the story with a voice question
  - 'ping':           Keep-alive heartbeat

The 'ask_question' flow triggers the full orchestration pipeline
(sanitize → Databricks RAG → spoiler guard → prompt synthesis)
and pushes the result back over the WebSocket in real-time.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.models.requests import WebSocketMessage
from app.services.databricks_client import DatabricksClient
from app.services.prompt_engine import PromptEngine
from app.services.sanitizer import QuerySanitizer
from app.services.spoiler_guard import SpoilerGuard

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

# Service instances
_databricks_client = DatabricksClient()
_prompt_engine = PromptEngine()
_spoiler_guard = SpoilerGuard()
_sanitizer = QuerySanitizer()

if TYPE_CHECKING:
    from app.services.session_manager import SessionManager


def _get_session_manager():
    """Get the session manager from the session router module (shared instance)."""
    from app.routers.session import session_manager
    return session_manager


async def _handle_context_update(
    ws: WebSocket,
    msg: WebSocketMessage,
    session_manager: SessionManager,
    session_id: str,
) -> None:
    """Process a rolling context / playback state update from the extension."""
    session_manager.update_session(
        session_id=session_id,
        episode_index=msg.episode_index,
        timestamp=msg.timestamp,
        rolling_context=msg.rolling_context,
    )
    await ws.send_json({
        "type": "context_ack",
        "status": "ok",
    })


async def _handle_ask_question(
    ws: WebSocket,
    msg: WebSocketMessage,
    session_manager: SessionManager,
    session_id: str,
) -> None:
    """
    Full orchestration pipeline triggered by a user question.
    Mirrors the /api/generate-prompt REST endpoint but over WebSocket.
    """
    start_time = time.perf_counter()

    # Validate question
    if not msg.user_query:
        await ws.send_json({
            "type": "error",
            "detail": "user_query is required for 'ask_question' type.",
        })
        return

    # Get session state for context
    session = session_manager.get_session(session_id)
    if session is None:
        await ws.send_json({
            "type": "error",
            "detail": f"Session '{session_id}' not found or expired.",
        })
        return

    # Use message values or fall back to session state
    rolling_context = msg.rolling_context or session.rolling_context
    episode_index = msg.episode_index or session.episode_index

    # Step 1: Sanitize user input
    sanitized_query = _sanitizer.sanitize(msg.user_query)
    if not sanitized_query:
        await ws.send_json({
            "type": "error",
            "detail": "User query is empty after sanitization.",
        })
        return

    logger.info(
        "WS ask_question: session=%s | query='%s' | episode=%d",
        session_id,
        sanitized_query[:80],
        episode_index,
    )

    # Step 2: Extract entities for optimized query
    entities = _prompt_engine.extract_entities(
        f"{sanitized_query} {rolling_context}"
    )
    optimized_query = sanitized_query
    if entities:
        entity_str = ", ".join(entities[:5])
        optimized_query = f"{sanitized_query} [Entities: {entity_str}]"

    # Step 3: Query Databricks for lore
    try:
        databricks_result = await _databricks_client.query_lore(
            query=optimized_query,
            current_context=rolling_context,
            max_episode_index=episode_index,
            top_k=5,
        )
    except Exception as e:
        logger.error("WS Databricks query failed: %s", str(e))
        await ws.send_json({
            "type": "error",
            "detail": "Failed to retrieve lore from knowledge base.",
        })
        return

    retrieved_chunks = databricks_result.get("retrieved_chunks", [])
    character_profile = databricks_result.get("character_profile")

    # Step 4: Spoiler guard
    safe_chunks = _spoiler_guard.validate(
        retrieved_chunks=retrieved_chunks,
        max_episode_index=episode_index,
    )

    # Step 5: Synthesize persona prompt
    prompt_result = _prompt_engine.synthesize(
        user_query=sanitized_query,
        rolling_context=rolling_context,
        retrieved_chunks=safe_chunks,
        character_profile=character_profile,
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "WS prompt generated in %.1fms | character=%s | lore_chunks=%d",
        elapsed_ms,
        prompt_result["active_character"],
        len(safe_chunks),
    )

    # Push result to client
    await ws.send_json({
        "type": "prompt_response",
        "system_instructions": prompt_result["system_instructions"],
        "voice_settings": prompt_result["voice_settings"],
        "user_input": prompt_result["user_input"],
        "active_character": prompt_result["active_character"],
        "processing_time_ms": round(elapsed_ms, 1),
    })


@router.websocket("/ws/session/{session_id}")
async def websocket_session(ws: WebSocket, session_id: str) -> None:
    """
    Bi-directional WebSocket endpoint for a specific session.

    The client connects with an existing session_id (created via
    POST /api/session). Messages are JSON objects with a 'type' field.

    Supported message types:
      - 'context_update': Push rolling context and playback state
      - 'ask_question':   Trigger the full orchestration pipeline
      - 'ping':           Keep-alive (responds with 'pong')
    """
    sm = _get_session_manager()

    # Validate session exists
    session = sm.get_session(session_id)
    if session is None:
        await ws.close(code=4004, reason=f"Session '{session_id}' not found")
        return

    await ws.accept()
    logger.info("WebSocket connected: session=%s", session_id)

    try:
        while True:
            # Receive message
            raw_data = await ws.receive_text()

            try:
                data = json.loads(raw_data)
                msg = WebSocketMessage(**data)
            except (json.JSONDecodeError, ValidationError) as e:
                await ws.send_json({
                    "type": "error",
                    "detail": f"Invalid message format: {str(e)[:200]}",
                })
                continue

            # Route by message type
            if msg.type == "context_update":
                await _handle_context_update(ws, msg, sm, session_id)

            elif msg.type == "ask_question":
                await _handle_ask_question(ws, msg, sm, session_id)

            elif msg.type == "ping":
                session = sm.get_session(session_id)
                if session:
                    session.touch()
                await ws.send_json({"type": "pong"})

            else:
                await ws.send_json({
                    "type": "error",
                    "detail": f"Unknown message type: '{msg.type}'. "
                    "Supported: 'context_update', 'ask_question', 'ping'.",
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session=%s", session_id)
    except Exception:
        logger.exception("WebSocket error: session=%s", session_id)
        try:
            await ws.close(code=1011, reason="Internal server error")
        except Exception:
            pass

"""
WhisperNet Backend — Context & Prompt Generation Router

This is the primary orchestration endpoint — the heart of Member 3's
deliverable. It receives the user's question + rolling context from the
extension, queries Databricks for lore, enforces spoiler boundaries,
and synthesizes the complete persona prompt for OpenAI Realtime.
"""

import logging
import time

from fastapi import APIRouter, HTTPException

from app.models.requests import GeneratePromptRequest
from app.models.responses import ErrorResponse, GeneratePromptResponse, VoiceSettings
from app.services.databricks_client import DatabricksClient
from app.services.prompt_engine import PromptEngine
from app.services.sanitizer import QuerySanitizer
from app.services.spoiler_guard import SpoilerGuard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Context & Prompt Generation"])

# Service instances
_databricks_client = DatabricksClient()
_prompt_engine = PromptEngine()
_spoiler_guard = SpoilerGuard()
_sanitizer = QuerySanitizer()


@router.post(
    "/generate-prompt",
    response_model=GeneratePromptResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid or empty user query"},
        500: {"model": ErrorResponse, "description": "Internal processing error"},
    },
    summary="Generate persona prompt from context",
    description=(
        "The main orchestration endpoint. Receives the user's transcribed question "
        "and the rolling story context, queries Databricks for relevant lore (with "
        "spoiler filtering), and returns a fully synthesized persona prompt ready "
        "for the OpenAI Realtime API."
    ),
)
async def generate_prompt(request: GeneratePromptRequest) -> GeneratePromptResponse:
    """
    Orchestration pipeline:
    1. Sanitize user query (prompt injection defense)
    2. Extract entities from query + context for optimized retrieval
    3. Query Databricks for relevant lore (episode-capped)
    4. Apply spoiler guard (defense-in-depth filtering)
    5. Synthesize persona prompt with dynamic tone matching
    6. Return complete payload for OpenAI Realtime
    """
    start_time = time.perf_counter()

    # ── Step 1: Sanitize user input ──
    sanitized_query = _sanitizer.sanitize(request.user_query) if request.user_query else ""

    logger.info(
        "Generate prompt request: query='%s' | episode=%d | context_len=%d",
        sanitized_query[:80],
        request.playback_state.episode_index,
        len(request.rolling_context),
    )

    # ── Step 2: Extract entities for optimized Databricks query ──
    entities = _prompt_engine.extract_entities(
        f"{sanitized_query} {request.rolling_context}"
    )
    optimized_query = sanitized_query
    if entities:
        entity_str = ", ".join(entities[:5])
        optimized_query = f"{sanitized_query} [Entities: {entity_str}]"
        logger.debug("Extracted entities: %s", entity_str)

    if not optimized_query.strip():
        optimized_query = "Solo Leveling lore context"

    # ── Step 3: Query Databricks for lore ──
    try:
        databricks_result = await _databricks_client.query_lore(
            query=optimized_query,
            current_context=request.rolling_context,
            max_episode_index=request.playback_state.episode_index,
            top_k=5,
        )
    except Exception as e:
        logger.error("Databricks query failed: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve lore from knowledge base.",
        ) from e

    retrieved_chunks = databricks_result.get("retrieved_chunks", [])
    character_profile = databricks_result.get("character_profile")

    # ── Step 4: Spoiler guard (defense-in-depth) ──
    safe_chunks = _spoiler_guard.validate(
        retrieved_chunks=retrieved_chunks,
        max_episode_index=request.playback_state.episode_index,
    )

    # ── Step 5: Synthesize persona prompt ──
    prompt_result = _prompt_engine.synthesize(
        user_query=sanitized_query,
        rolling_context=request.rolling_context,
        retrieved_chunks=safe_chunks,
        character_profile=character_profile,
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "Prompt generated in %.1fms | character=%s | lore_chunks=%d",
        elapsed_ms,
        prompt_result["active_character"],
        len(safe_chunks),
    )

    # ── Step 6: Return response ──
    voice_settings_data = prompt_result.get("voice_settings", {})
    return GeneratePromptResponse(
        system_instructions=prompt_result["system_instructions"],
        voice_settings=VoiceSettings(**voice_settings_data),
        user_input=prompt_result["user_input"],
        active_character=prompt_result["active_character"],
    )

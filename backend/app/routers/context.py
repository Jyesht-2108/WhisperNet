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
        optimized_query = "Story lore context"

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

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────
# /api/search-lore — Realtime Tool Calling Endpoint
# ─────────────────────────────────────────────────────────────
# This is the endpoint that OpenAI's Realtime model calls MID-CONVERSATION
# when the user asks about a character/event. Instead of pre-loading generic
# lore into the system prompt, the AI triggers this tool on-demand to fetch
# only the specific chunks it needs (~250 tokens), keeping the total prompt
# payload under ~800 tokens.
# ─────────────────────────────────────────────────────────────

class SearchLoreRequest(BaseModel):
    """Payload for the search-lore tool call from OpenAI Realtime."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="The user's question or the specific entity/event to look up.",
    )
    episode_index: int = Field(
        default=999,
        ge=1,
        description="Spoiler ceiling — only return lore from this episode or earlier.",
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of relevant chunks to retrieve.",
    )


@router.post(
    "/search-lore",
    summary="Realtime Tool Call — Search Lore",
    description=(
        "Direct lore lookup endpoint designed for OpenAI Realtime Tool Calling. "
        "When the user speaks over WebRTC and asks about a character or event, "
        "the AI model automatically calls this tool to fetch the specific lore "
        "chunks from Databricks mid-conversation, instead of pre-loading the "
        "entire episode transcript."
    ),
)
async def search_lore(request: SearchLoreRequest) -> dict:
    """
    Realtime Tool Calling flow:
    1. User asks "Why did Jake go to lunch with Jacob?" over WebRTC
    2. OpenAI Realtime model triggers `search_lore` tool automatically
    3. This endpoint queries Databricks Vector Search with spoiler filtering
    4. Returns only the 2-3 most relevant chunks (~250 tokens total)
    5. OpenAI uses these chunks to answer accurately and in-character
    """
    start_time = time.perf_counter()

    logger.info(
        "Tool call search-lore: query='%s' | episode_cap=%d | top_k=%d",
        request.query[:80],
        request.episode_index,
        request.top_k,
    )

    try:
        databricks_result = await _databricks_client.query_lore(
            query=request.query,
            current_context="",
            max_episode_index=request.episode_index,
            top_k=request.top_k,
        )

        chunks = databricks_result.get("retrieved_chunks", [])
        status = databricks_result.get("retrieval_status", "ERROR")

        # Build a lean text payload for the AI — only the text fields
        context_snippets = [chunk["text"] for chunk in chunks if chunk.get("text")]
        combined_context = "\n---\n".join(context_snippets)

        # Collect source episode indices for citation
        sources = list({chunk.get("episode_index", 0) for chunk in chunks})

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "search-lore completed in %.1fms | chunks=%d | status=%s",
            elapsed_ms, len(chunks), status,
        )

        return {
            "retrieved_context": combined_context,
            "sources": sorted(sources),
            "retrieval_status": status,
            "chunk_count": len(chunks),
        }

    except Exception as e:
        logger.error("Tool search-lore failed: %s", str(e))
        return {
            "retrieved_context": "",
            "sources": [],
            "retrieval_status": "ERROR",
            "chunk_count": 0,
        }


# ─────────────────────────────────────────────────────────────
# /api/tool-schema — OpenAI Tool Definition for Member 4
# ─────────────────────────────────────────────────────────────

SEARCH_LORE_TOOL_DEFINITION = {
    "type": "function",
    "name": "search_lore",
    "description": (
        "Search the story knowledge base for specific character information, "
        "plot events, or world-building details. Use this tool whenever the "
        "user asks about a character, event, or detail from the story. "
        "The results are filtered to prevent spoilers beyond the current episode."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The search query — what the user is asking about. "
                    "Example: 'Why did Jake go to lunch with Jacob?'"
                ),
            },
            "episode_index": {
                "type": "integer",
                "description": (
                    "The current episode number the user is listening to. "
                    "Only lore from this episode or earlier will be returned."
                ),
            },
        },
        "required": ["query"],
    },
}


@router.get(
    "/tool-schema",
    summary="Get OpenAI tool definitions",
    description=(
        "Returns the JSON tool definition for `search_lore` that Member 4 "
        "registers with OpenAI's Realtime API via `session.update`."
    ),
)
async def get_tool_schema() -> dict:
    """Return the tool definitions for OpenAI Realtime session configuration."""
    return {"tools": [SEARCH_LORE_TOOL_DEFINITION]}

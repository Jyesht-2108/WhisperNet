"""
WhisperNet Backend — Databricks Client

Handles retrieval of story lore from Member 2's Databricks
Model Serving endpoint. Includes a comprehensive mock mode
for local development without a live Databricks instance.
"""

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Mock Data — Realistic Solo Leveling lore for local dev/testing
# ─────────────────────────────────────────────────────────────
_MOCK_LORE_DATABASE: list[dict[str, Any]] = [
    {
        "id": "lore-001",
        "text": (
            "Sung Jin-Woo is an E-Rank Hunter, widely known as 'The Weakest Weapon' "
            "among all registered Hunters in South Korea. Despite being the lowest "
            "rank, he continues dungeon raiding to pay for his mother's hospital bills. "
            "He is part of a raiding party that enters low-level dungeons for minimal "
            "rewards."
        ),
        "episode_index": 1,
        "character_tags": ["Sung Jin-Woo"],
        "persona_traits": ["Desperate", "Determined", "Humble", "Resilient"],
        "voice_tone": "Quiet, self-deprecating, cautiously observant",
    },
    {
        "id": "lore-002",
        "text": (
            "The Double Dungeon is a hidden dungeon within a D-Rank dungeon. It is "
            "an ancient temple known as the Cartenon Temple, filled with massive stone "
            "statues that serve as guardians. The temple contains a set of commandments "
            "inscribed on a stone tablet — the 'Commandments of the Statue of God.' "
            "Breaking any commandment triggers the statues to attack."
        ),
        "episode_index": 2,
        "character_tags": ["Statue of God", "Cartenon Temple"],
        "persona_traits": [],
        "voice_tone": "Ominous, heavy, echoing",
    },
    {
        "id": "lore-003",
        "text": (
            "Inside the Cartenon Temple, a colossal stone statue sits on a throne — "
            "the Statue of God. It has a serene smile but glowing red eyes that track "
            "every hunter in the room. When the commandments are broken, smaller angel "
            "statues come alive wielding stone weapons, while the Statue of God itself "
            "begins to move with terrifying power."
        ),
        "episode_index": 3,
        "character_tags": ["Statue of God", "Angel Statues"],
        "persona_traits": [],
        "voice_tone": "Terrifying, imposing, ancient",
    },
    {
        "id": "lore-004",
        "text": (
            "After barely surviving the Cartenon Temple massacre, Jin-Woo is offered "
            "a choice by a mysterious System: accept the 'Player' role or die. He "
            "accepts, becoming the sole recipient of the System — a game-like interface "
            "that only he can see, granting him quests, stats, and the ability to level "
            "up beyond the normal Hunter ranking system."
        ),
        "episode_index": 4,
        "character_tags": ["Sung Jin-Woo", "The System"],
        "persona_traits": ["Confused", "Determined", "Awakening"],
        "voice_tone": "Breathless, shocked, resolve building",
    },
    {
        "id": "lore-005",
        "text": (
            "The System assigns Jin-Woo daily quests: 100 push-ups, 100 sit-ups, "
            "100 squats, and a 10km run. Failure to complete them results in a "
            "'Penalty Quest' — being sent to a punishment dungeon. Through these "
            "grueling exercises, Jin-Woo begins his transformation from E-Rank to "
            "something far more powerful."
        ),
        "episode_index": 5,
        "character_tags": ["Sung Jin-Woo", "The System"],
        "persona_traits": ["Disciplined", "Growing", "Secretive"],
        "voice_tone": "Exhausted but determined, inner monologue",
    },
    {
        "id": "lore-006",
        "text": (
            "Yoo Jin-Ho is the son of the wealthy Yoo Myung-Han, chairman of the "
            "Yoojin Construction conglomerate. Despite being a D-Rank Hunter, Jin-Ho "
            "is earnest and loyal. He forms a partnership with Jin-Woo, initially to "
            "complete dungeon raid requirements, but gradually becomes Jin-Woo's most "
            "trusted ally and vice-guild master."
        ),
        "episode_index": 6,
        "character_tags": ["Yoo Jin-Ho", "Sung Jin-Woo"],
        "persona_traits": ["Loyal", "Earnest", "Wealthy", "Eager"],
        "voice_tone": "Enthusiastic, respectful, slightly nervous",
    },
    {
        "id": "lore-007",
        "text": (
            "The Hunter's Association is the government body that manages all Hunter "
            "activities in South Korea. They oversee dungeon gate monitoring, raid "
            "permits, and Hunter rankings. The current chairman, Go Gun-Hee, is an "
            "elderly but powerful S-Rank Hunter who takes a personal interest in "
            "Jin-Woo's unprecedented growth."
        ),
        "episode_index": 7,
        "character_tags": ["Hunter's Association", "Go Gun-Hee"],
        "persona_traits": ["Wise", "Curious", "Authoritative"],
        "voice_tone": "Calm, measured, gravitas",
    },
    {
        "id": "lore-008",
        "text": (
            "Shadow Extraction is Jin-Woo's signature ability as the Shadow Monarch's "
            "vessel. He can extract the shadows of defeated enemies, turning them into "
            "loyal shadow soldiers under his command. His first major extraction creates "
            "Igris, a powerful knight shadow from the Cartenon Temple's Red Knight boss."
        ),
        "episode_index": 8,
        "character_tags": ["Sung Jin-Woo", "Igris", "Shadow Soldiers"],
        "persona_traits": ["Commanding", "Strategic", "Growing Power"],
        "voice_tone": "Confident, commanding, dark undertone",
    },
]

# Character profiles for persona generation
_CHARACTER_PROFILES: dict[str, dict[str, Any]] = {
    "Sung Jin-Woo": {
        "name": "Sung Jin-Woo",
        "default_traits": ["Determined", "Strategic", "Protective"],
        "default_tone": "Calm, analytical, quietly intense",
    },
    "Yoo Jin-Ho": {
        "name": "Yoo Jin-Ho",
        "default_traits": ["Loyal", "Earnest", "Eager"],
        "default_tone": "Enthusiastic, respectful, slightly nervous",
    },
    "Narrator": {
        "name": "Narrator",
        "default_traits": ["Omniscient", "Dramatic", "Foreboding"],
        "default_tone": "Deep, measured, building tension",
    },
}


class DatabricksClient:
    """
    Client for querying Member 2's Databricks Model Serving endpoint.
    Supports a mock mode for local development.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.use_mock = self.settings.USE_MOCK_DATABRICKS

    async def query_lore(
        self,
        query: str,
        current_context: str,
        max_episode_index: int,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """
        Query the knowledge base for relevant lore.

        Args:
            query: The user's question / search text.
            current_context: Recent rolling transcript for entity detection.
            max_episode_index: Hard ceiling for spoiler prevention.
            top_k: Number of chunks to retrieve.

        Returns:
            Dict with 'retrieved_chunks', 'character_profile', and 'retrieval_status'.
        """
        if self.use_mock:
            return self._mock_query(query, current_context, max_episode_index, top_k)

        return await self._live_query(query, current_context, max_episode_index, top_k)

    async def _live_query(
        self,
        query: str,
        current_context: str,
        max_episode_index: int,
        top_k: int,
    ) -> dict[str, Any]:
        """Execute a live query against Member 2's Databricks endpoint."""
        payload = {
            "columns": ["id", "text", "episode_index", "character_tags"],
            "query_text": f"{query} {current_context}".strip(),
            "num_results": top_k,
            "filters": {"episode_index <=": max_episode_index}
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.settings.DATABRICKS_ENDPOINT_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.settings.DATABRICKS_API_TOKEN}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                
                # Databricks Vector Search returns data in `result.data_array`
                retrieved_chunks = []
                if "result" in data and "data_array" in data["result"]:
                    for row in data["result"]["data_array"]:
                        if len(row) >= 2:
                            retrieved_chunks.append({
                                "id": row[0],
                                "text": row[1],
                                "episode_index": row[2] if len(row) > 2 else 0,
                                "character_tags": row[3] if len(row) > 3 else []
                            })

                return {
                    "retrieved_chunks": retrieved_chunks,
                    "character_profile": None,
                    "retrieval_status": "SUCCESS",
                }

        except httpx.HTTPStatusError as e:
            logger.error("Databricks API returned %d: %s", e.response.status_code, e.response.text)
            return {"retrieved_chunks": [], "character_profile": None, "retrieval_status": "ERROR"}
        except httpx.RequestError as e:
            logger.error("Databricks API request failed: %s", str(e))
            return {"retrieved_chunks": [], "character_profile": None, "retrieval_status": "ERROR"}

    def _mock_query(
        self,
        query: str,
        current_context: str,
        max_episode_index: int,
        top_k: int,
    ) -> dict[str, Any]:
        """
        Return mock Solo Leveling lore data, filtered by episode index.
        Performs basic keyword matching for relevance.
        """
        query_lower = query.lower()
        context_lower = current_context.lower()
        combined_text = f"{query_lower} {context_lower}"

        # Filter by episode cap first (spoiler prevention)
        eligible_chunks = [
            chunk for chunk in _MOCK_LORE_DATABASE if chunk["episode_index"] <= max_episode_index
        ]

        # Score chunks by keyword relevance
        scored_chunks: list[tuple[float, dict]] = []
        for chunk in eligible_chunks:
            score = 0.0
            chunk_text_lower = chunk["text"].lower()

            # Check character tag matches
            for tag in chunk.get("character_tags", []):
                if tag.lower() in combined_text:
                    score += 3.0

            # Check keyword overlap
            query_words = set(query_lower.split())
            chunk_words = set(chunk_text_lower.split())
            overlap = len(query_words & chunk_words)
            score += overlap * 0.5

            # Boost chunks closer to current episode
            episode_proximity = max_episode_index - chunk["episode_index"]
            score += max(0, 2.0 - (episode_proximity * 0.3))

            scored_chunks.append((score, chunk))

        # Sort by score (descending) and take top_k
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_chunks = [chunk for _, chunk in scored_chunks[:top_k]]

        # Detect primary character from context
        character_profile = None
        for name, profile in _CHARACTER_PROFILES.items():
            if name.lower() in combined_text:
                character_profile = {
                    "name": profile["name"],
                    "persona_traits": profile["default_traits"],
                    "voice_tone": profile["default_tone"],
                }
                break

        # Default to Narrator if no character detected
        if character_profile is None:
            narrator = _CHARACTER_PROFILES["Narrator"]
            character_profile = {
                "name": narrator["name"],
                "persona_traits": narrator["default_traits"],
                "voice_tone": narrator["default_tone"],
            }

        logger.info(
            "Mock Databricks query: '%s' | episode_cap=%d | results=%d | character=%s",
            query[:60],
            max_episode_index,
            len(top_chunks),
            character_profile["name"],
        )

        return {
            "retrieved_chunks": top_chunks,
            "character_profile": character_profile,
            "retrieval_status": "SUCCESS",
        }

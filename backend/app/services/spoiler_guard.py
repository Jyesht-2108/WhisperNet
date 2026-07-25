"""
WhisperNet Backend — Spoiler Guard

Secondary safety net that validates retrieved Databricks lore
does not contain data from episodes beyond the user's current
playback position. This is a defense-in-depth measure even if
Databricks correctly filters during vector search.
"""

import logging

logger = logging.getLogger(__name__)


class SpoilerGuard:
    """
    Validates that no retrieved lore exceeds the user's current
    episode boundary. Acts as a hard ceiling enforcement layer.
    """

    @staticmethod
    def validate(
        retrieved_chunks: list[dict],
        max_episode_index: int,
    ) -> list[dict]:
        """
        Filter retrieved lore chunks, removing any that exceed
        the maximum allowed episode index.

        Args:
            retrieved_chunks: List of lore chunk dicts, each containing
                              at minimum an 'episode_index' field.
            max_episode_index: The hard ceiling — no data from episodes
                               above this number is allowed through.

        Returns:
            Filtered list with only spoiler-safe chunks.
        """
        safe_chunks = []
        blocked_count = 0

        for chunk in retrieved_chunks:
            chunk_episode = chunk.get("episode_index", 0)

            if chunk_episode <= max_episode_index:
                safe_chunks.append(chunk)
            else:
                blocked_count += 1
                logger.warning(
                    "Spoiler guard blocked chunk from episode %d "
                    "(user ceiling: %d): %.80s...",
                    chunk_episode,
                    max_episode_index,
                    chunk.get("text", ""),
                )

        if blocked_count > 0:
            logger.info(
                "Spoiler guard: %d chunks passed, %d blocked (ceiling: episode %d)",
                len(safe_chunks),
                blocked_count,
                max_episode_index,
            )

        return safe_chunks

    @staticmethod
    def is_safe(chunk: dict, max_episode_index: int) -> bool:
        """Check if a single chunk is within the spoiler boundary."""
        return chunk.get("episode_index", 0) <= max_episode_index

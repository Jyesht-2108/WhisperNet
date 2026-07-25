"""Tests for the Databricks Client service (mock mode)."""

from app.services.databricks_client import DatabricksClient


# Force mock mode for testing
client = DatabricksClient()
client.use_mock = True


# ── Episode Filtering ──


def test_mock_query_respects_episode_cap():
    """Mock query should only return chunks at or below the episode cap."""
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        client.query_lore(
            query="Who is Jin-Woo?",
            current_context="Jin-Woo is fighting in the dungeon.",
            max_episode_index=3,
            top_k=10,
        )
    )

    for chunk in result["retrieved_chunks"]:
        assert chunk["episode_index"] <= 3, (
            f"Chunk from episode {chunk['episode_index']} leaked through cap of 3"
        )


def test_mock_query_episode_1_only():
    """With episode_index=1, only episode 1 lore should be returned."""
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        client.query_lore(
            query="Who is Jin-Woo?",
            current_context="The hunter entered the dungeon.",
            max_episode_index=1,
            top_k=10,
        )
    )

    for chunk in result["retrieved_chunks"]:
        assert chunk["episode_index"] == 1


def test_mock_query_high_episode_returns_more():
    """Higher episode cap should allow more chunks."""
    import asyncio

    result_low = asyncio.get_event_loop().run_until_complete(
        client.query_lore(
            query="Tell me about the story",
            current_context="",
            max_episode_index=2,
            top_k=10,
        )
    )

    result_high = asyncio.get_event_loop().run_until_complete(
        client.query_lore(
            query="Tell me about the story",
            current_context="",
            max_episode_index=8,
            top_k=10,
        )
    )

    assert len(result_high["retrieved_chunks"]) >= len(result_low["retrieved_chunks"])


# ── Character Detection ──


def test_mock_query_detects_jin_woo():
    """Mentioning 'Jin-Woo' should return Jin-Woo character profile."""
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        client.query_lore(
            query="Who is Sung Jin-Woo?",
            current_context="",
            max_episode_index=5,
            top_k=3,
        )
    )

    profile = result["character_profile"]
    assert profile is not None
    assert profile["name"] == "Sung Jin-Woo"
    assert "persona_traits" in profile
    assert "voice_tone" in profile


def test_mock_query_detects_jin_ho():
    """Mentioning 'Jin-Ho' should return Jin-Ho character profile."""
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        client.query_lore(
            query="Tell me about Yoo Jin-Ho",
            current_context="",
            max_episode_index=7,
            top_k=3,
        )
    )

    profile = result["character_profile"]
    assert profile is not None
    assert profile["name"] == "Yoo Jin-Ho"


def test_mock_query_defaults_to_narrator():
    """Without character mentions, should default to Narrator profile."""
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        client.query_lore(
            query="What is happening in this scene?",
            current_context="A mysterious light appeared.",
            max_episode_index=3,
            top_k=3,
        )
    )

    profile = result["character_profile"]
    assert profile is not None
    assert profile["name"] == "Narrator"


# ── Relevance Scoring ──


def test_mock_query_relevance_scoring():
    """Querying about 'statue' should prioritize statue-related chunks."""
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        client.query_lore(
            query="Who is the giant statue in the dungeon?",
            current_context="The statues began to move, their eyes glowing red.",
            max_episode_index=5,
            top_k=3,
        )
    )

    chunks = result["retrieved_chunks"]
    assert len(chunks) > 0

    # At least one chunk should mention statues
    has_statue = any("statue" in chunk["text"].lower() for chunk in chunks)
    assert has_statue


def test_mock_query_returns_retrieval_status():
    """Mock queries should always return SUCCESS status."""
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        client.query_lore(
            query="test",
            current_context="test",
            max_episode_index=1,
            top_k=1,
        )
    )

    assert result["retrieval_status"] == "SUCCESS"


# ── Top-K Limiting ──


def test_mock_query_respects_top_k():
    """Should return at most top_k chunks."""
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        client.query_lore(
            query="Tell me everything",
            current_context="",
            max_episode_index=8,
            top_k=2,
        )
    )

    assert len(result["retrieved_chunks"]) <= 2

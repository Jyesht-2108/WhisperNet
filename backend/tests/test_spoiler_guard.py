"""Tests for the Spoiler Guard service."""

from app.services.spoiler_guard import SpoilerGuard

guard = SpoilerGuard()


def test_all_chunks_within_boundary():
    """All chunks at or below the cap should pass through."""
    chunks = [
        {"text": "Episode 1 lore", "episode_index": 1},
        {"text": "Episode 2 lore", "episode_index": 2},
        {"text": "Episode 3 lore", "episode_index": 3},
    ]
    result = guard.validate(chunks, max_episode_index=3)
    assert len(result) == 3


def test_blocks_future_episodes():
    """Chunks above the episode cap should be filtered out."""
    chunks = [
        {"text": "Episode 1 lore", "episode_index": 1},
        {"text": "Episode 5 spoiler!", "episode_index": 5},
        {"text": "Episode 8 mega spoiler!", "episode_index": 8},
    ]
    result = guard.validate(chunks, max_episode_index=3)
    assert len(result) == 1
    assert result[0]["episode_index"] == 1


def test_exact_boundary():
    """Chunks at exactly the max episode should pass."""
    chunks = [
        {"text": "Exactly at boundary", "episode_index": 3},
    ]
    result = guard.validate(chunks, max_episode_index=3)
    assert len(result) == 1


def test_all_blocked():
    """If all chunks are from future episodes, return empty list."""
    chunks = [
        {"text": "Future lore 1", "episode_index": 10},
        {"text": "Future lore 2", "episode_index": 15},
    ]
    result = guard.validate(chunks, max_episode_index=3)
    assert len(result) == 0


def test_empty_chunks():
    """Empty input should return empty output."""
    result = guard.validate([], max_episode_index=5)
    assert result == []


def test_missing_episode_index_defaults_zero():
    """Chunks without episode_index should default to 0 (always passes)."""
    chunks = [
        {"text": "Generic lore without episode tag"},
    ]
    result = guard.validate(chunks, max_episode_index=1)
    assert len(result) == 1


def test_is_safe_individual():
    """Test individual chunk safety check."""
    assert guard.is_safe({"episode_index": 3}, max_episode_index=5) is True
    assert guard.is_safe({"episode_index": 6}, max_episode_index=5) is False
    assert guard.is_safe({"episode_index": 5}, max_episode_index=5) is True

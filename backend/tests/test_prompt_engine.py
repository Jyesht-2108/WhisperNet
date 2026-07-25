"""Tests for the Persona Prompt Engine."""

from app.services.prompt_engine import PromptEngine


engine = PromptEngine()


def test_detect_scene_mood_tense():
    """Tense keywords should be detected."""
    context = "The hunters screamed in terror as the attack began. Blood splattered everywhere."
    mood = engine.detect_scene_mood(context)
    assert "tense" in mood


def test_detect_scene_mood_calm():
    """Calm keywords should be detected."""
    context = "The morning sun warmed the peaceful village. Jin-Woo smiled gently."
    mood = engine.detect_scene_mood(context)
    assert "calm" in mood


def test_detect_scene_mood_neutral():
    """Generic text without mood keywords should return neutral."""
    context = "The man walked to the store and bought some groceries."
    mood = engine.detect_scene_mood(context)
    assert mood == "neutral"


def test_synthesize_with_character():
    """Prompt synthesis with a character profile produces character-specific output."""
    result = engine.synthesize(
        user_query="Who are you?",
        rolling_context="Jin-Woo stood before the massive dungeon gate.",
        retrieved_chunks=[
            {
                "text": "Sung Jin-Woo is an E-Rank Hunter.",
                "episode_index": 1,
                "character_tags": ["Sung Jin-Woo"],
            }
        ],
        character_profile={
            "name": "Sung Jin-Woo",
            "persona_traits": ["Determined", "Humble"],
            "voice_tone": "Quiet, observant",
        },
    )

    assert "Sung Jin-Woo" in result["system_instructions"]
    assert result["active_character"] == "Sung Jin-Woo"
    assert "user_input" in result
    assert "voice_settings" in result


def test_synthesize_without_character_uses_narrator():
    """Without a character profile, should default to Narrator."""
    result = engine.synthesize(
        user_query="What is happening?",
        rolling_context="The dungeon rumbled ominously.",
        retrieved_chunks=[],
        character_profile=None,
    )

    assert result["active_character"] == "Narrator"
    assert "narrator" in result["system_instructions"].lower()


def test_format_lore_chunks_empty():
    """Empty chunks should produce a no-data message."""
    formatted = engine.format_lore_chunks([])
    assert "no additional lore" in formatted.lower()


def test_format_lore_chunks_with_data():
    """Chunks should be formatted with episode and character metadata."""
    formatted = engine.format_lore_chunks([
        {
            "text": "Jin-Woo is an E-Rank Hunter.",
            "episode_index": 1,
            "character_tags": ["Sung Jin-Woo"],
        }
    ])
    assert "Episode 1" in formatted
    assert "Jin-Woo" in formatted
    assert "Sung Jin-Woo" in formatted

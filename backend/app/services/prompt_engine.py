"""
WhisperNet Backend — Persona Prompt Engine

The core intelligence synthesizer. Merges user query, rolling transcript
context, Databricks lore, and character persona into a single, cohesive
system prompt for the OpenAI Realtime API.
"""

import logging
from typing import Any

from app.prompts.templates import (
    NARRATOR_SYSTEM_PROMPT,
    PERSONA_SYSTEM_PROMPT,
    TONE_KEYWORDS,
)

logger = logging.getLogger(__name__)


class PromptEngine:
    """
    Synthesizes dynamic persona prompts by fusing:
    - Character persona (name, traits, voice tone)
    - Retrieved Databricks lore (filtered by spoiler guard)
    - Live rolling transcript (last 60-90s of story audio)
    - Scene mood detection (dynamic tone matching)
    """

    @staticmethod
    def detect_scene_mood(rolling_context: str) -> str:
        """
        Analyze the rolling transcript to determine the current scene's
        emotional tone. Used to dynamically adjust the AI's speaking style.

        Returns a comma-separated string of detected moods.
        """
        context_lower = rolling_context.lower()
        detected_moods: list[str] = []

        for mood, keywords in TONE_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in context_lower)
            if matches >= 2:
                detected_moods.append(mood)

        return ", ".join(detected_moods) if detected_moods else "neutral"

    @staticmethod
    def extract_entities(text: str) -> list[str]:
        """
        Extract potential character names and entity references from text.
        Uses capitalization heuristics as a lightweight NER approach.
        """
        words = text.split()
        entities: list[str] = []
        i = 0

        while i < len(words):
            word = words[i].strip(".,!?;:\"'()[]")

            # Look for capitalized multi-word names (e.g., "Sung Jin-Woo")
            if word and word[0].isupper() and not _is_sentence_start(words, i):
                name_parts = [word]
                j = i + 1
                while j < len(words):
                    next_word = words[j].strip(".,!?;:\"'()[]")
                    # Continue if next word is capitalized or a hyphenated continuation
                    if next_word and (next_word[0].isupper() or "-" in next_word):
                        name_parts.append(next_word)
                        j += 1
                    else:
                        break
                entity = " ".join(name_parts)
                if len(entity) > 2:
                    entities.append(entity)
                i = j
            else:
                i += 1

        return list(set(entities))

    @staticmethod
    def format_lore_chunks(chunks: list[dict[str, Any]]) -> str:
        """Format retrieved lore chunks into a readable text block."""
        if not chunks:
            return "No additional lore available for the current scene."

        formatted_parts: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("text", "")
            episode = chunk.get("episode_index", "?")
            characters = ", ".join(chunk.get("character_tags", []))
            header = f"[Fact {i} | Episode {episode}"
            if characters:
                header += f" | Characters: {characters}"
            header += "]"
            formatted_parts.append(f"{header}\n{text}")

        return "\n\n".join(formatted_parts)

    def synthesize(
        self,
        user_query: str,
        rolling_context: str,
        retrieved_chunks: list[dict[str, Any]],
        character_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate the complete system prompt and voice settings.

        Args:
            user_query: The sanitized user question.
            rolling_context: The last 60-90s of transcribed audio.
            retrieved_chunks: Spoiler-safe lore chunks from Databricks.
            character_profile: Detected character info (name, traits, tone).

        Returns:
            Dict containing 'system_instructions', 'voice_settings',
            'active_character', and 'user_input'.
        """
        # Detect scene mood for dynamic tone adjustment
        scene_mood = self.detect_scene_mood(rolling_context)

        # Format retrieved lore
        formatted_lore = self.format_lore_chunks(retrieved_chunks)

        # Determine character and build prompt
        if character_profile and character_profile.get("name") != "Narrator":
            character_name = character_profile["name"]
            traits = ", ".join(character_profile.get("persona_traits", []))
            base_tone = character_profile.get("voice_tone", "neutral")
            voice_tone = f"{base_tone} (current scene mood: {scene_mood})"

            system_instructions = PERSONA_SYSTEM_PROMPT.format(
                character_name=character_name,
                persona_traits=traits,
                voice_tone=voice_tone,
                rolling_context=rolling_context,
                retrieved_lore=formatted_lore,
            )
        else:
            character_name = "Narrator"
            voice_tone = f"Deep, measured, building tension (current scene mood: {scene_mood})"

            system_instructions = NARRATOR_SYSTEM_PROMPT.format(
                voice_tone=voice_tone,
                rolling_context=rolling_context,
                retrieved_lore=formatted_lore,
            )

        # Select voice ID based on character
        voice_id = _select_voice(character_name)

        logger.info(
            "Prompt synthesized: character=%s | mood=%s | lore_chunks=%d | prompt_len=%d",
            character_name,
            scene_mood,
            len(retrieved_chunks),
            len(system_instructions),
        )

        return {
            "system_instructions": system_instructions,
            "voice_settings": {
                "voice_id": voice_id,
                "speed": 1.0,
                "emotional_tone": scene_mood,
            },
            "active_character": character_name,
            "user_input": user_query,
        }


def _is_sentence_start(words: list[str], index: int) -> bool:
    """Check if a word is likely the start of a new sentence."""
    if index == 0:
        return True
    prev_word = words[index - 1]
    return prev_word.endswith((".", "!", "?", ":", '."', '!"', '?"'))


def _select_voice(character_name: str) -> str:
    """Map character names to OpenAI Realtime voice IDs."""
    voice_map = {
        "Sung Jin-Woo": "echo",
        "Yoo Jin-Ho": "shimmer",
        "Narrator": "alloy",
        "Go Gun-Hee": "onyx",
    }
    return voice_map.get(character_name, "alloy")

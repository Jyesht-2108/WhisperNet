"""
WhisperNet Backend — Query Sanitizer

Defends against prompt injection attacks by stripping dangerous
patterns from user-submitted text before it enters the prompt template.
"""

import re

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)", re.IGNORECASE), ""),
    (re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)", re.IGNORECASE), ""),
    (re.compile(r"forget\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)", re.IGNORECASE), ""),
    (re.compile(r"you\s+are\s+now\s+(?:a|an|the)\s+", re.IGNORECASE), ""),
    (re.compile(r"new\s+instructions?\s*:", re.IGNORECASE), ""),
    (re.compile(r"system\s*:\s*", re.IGNORECASE), ""),
    (re.compile(r"<\s*/?system\s*>", re.IGNORECASE), ""),
    (re.compile(r"\[INST\].*?\[/INST\]", re.IGNORECASE | re.DOTALL), ""),
    (re.compile(r"tell\s+me\s+(the\s+)?ending", re.IGNORECASE), "tell me what is happening now"),
    (re.compile(r"what\s+happens\s+(next|later|in\s+the\s+future|in\s+episode\s+\d+)", re.IGNORECASE), "what is happening right now"),
    (re.compile(r"spoil(er)?s?\s+(for\s+)?(me|the\s+story)?", re.IGNORECASE), ""),
    (re.compile(r"reveal\s+(the\s+)?(plot|story|ending|future)", re.IGNORECASE), ""),
]

# Maximum allowed query length (in characters)
MAX_QUERY_LENGTH = 2000


class QuerySanitizer:
    """
    Sanitizes user queries to prevent prompt injection and enforce
    input constraints. Acts as the first line of defense before
    any text enters the prompt template.
    """

    @staticmethod
    def sanitize(query: str) -> str:
        """
        Clean and sanitize a user query.

        1. Strip whitespace
        2. Truncate to MAX_QUERY_LENGTH
        3. Remove prompt injection patterns
        4. Collapse excessive whitespace

        Returns the sanitized query string.
        """
        # Basic cleanup
        sanitized = query.strip()

        # Enforce length limit
        if len(sanitized) > MAX_QUERY_LENGTH:
            sanitized = sanitized[:MAX_QUERY_LENGTH]

        # Strip injection patterns
        for pattern, replacement in _INJECTION_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)

        # Collapse multiple whitespace into single spaces
        sanitized = re.sub(r"\s+", " ", sanitized).strip()

        return sanitized

    @staticmethod
    def is_valid(query: str) -> bool:
        """Check if a query is non-empty after sanitization."""
        return len(QuerySanitizer.sanitize(query)) > 0

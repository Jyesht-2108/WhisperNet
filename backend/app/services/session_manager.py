"""
WhisperNet Backend — Session Manager

In-memory session store for tracking per-client state including
playback position, rolling context, and connection status.
Provides TTL-based expiry to prevent memory leaks from
abandoned sessions.
"""

import asyncio
import logging
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# Default session TTL: 30 minutes
DEFAULT_SESSION_TTL_SECONDS = 1800

# Cleanup interval: run garbage collection every 60 seconds
_CLEANUP_INTERVAL_SECONDS = 60


class Session:
    """Represents a single client session with tracked state."""

    __slots__ = (
        "session_id",
        "created_at",
        "last_active",
        "episode_index",
        "timestamp",
        "rolling_context",
        "is_active",
        "metadata",
    )

    def __init__(
        self,
        session_id: str,
        episode_index: int = 1,
        timestamp: float = 0.0,
    ) -> None:
        self.session_id = session_id
        self.created_at = time.time()
        self.last_active = time.time()
        self.episode_index = episode_index
        self.timestamp = timestamp
        self.rolling_context = ""
        self.is_active = True
        self.metadata: dict[str, Any] = {}

    def touch(self) -> None:
        """Update the last_active timestamp to extend TTL."""
        self.last_active = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Serialize session state for API responses."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "episode_index": self.episode_index,
            "timestamp": self.timestamp,
            "rolling_context_length": len(self.rolling_context),
            "is_active": self.is_active,
        }


class SessionManager:
    """
    Thread-safe, in-memory session manager with automatic TTL-based
    garbage collection for expired sessions.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS) -> None:
        self._sessions: dict[str, Session] = {}
        self._ttl_seconds = ttl_seconds
        self._cleanup_task: asyncio.Task | None = None

    # ── Lifecycle ──

    async def start_cleanup_loop(self) -> None:
        """Start the background cleanup task for expired sessions."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info(
                "Session cleanup loop started (TTL=%ds, interval=%ds)",
                self._ttl_seconds,
                _CLEANUP_INTERVAL_SECONDS,
            )

    async def stop_cleanup_loop(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Session cleanup loop stopped.")

    async def _cleanup_loop(self) -> None:
        """Periodically remove expired sessions."""
        while True:
            try:
                await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)
                removed = self._purge_expired()
                if removed > 0:
                    logger.info(
                        "Session cleanup: removed %d expired sessions (%d active)",
                        removed,
                        len(self._sessions),
                    )
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in session cleanup loop")

    def _purge_expired(self) -> int:
        """Remove all sessions that have exceeded their TTL. Returns count removed."""
        now = time.time()
        expired_ids = [
            sid
            for sid, session in self._sessions.items()
            if (now - session.last_active) > self._ttl_seconds
        ]
        for sid in expired_ids:
            del self._sessions[sid]
        return len(expired_ids)

    # ── CRUD Operations ──

    def create_session(
        self,
        episode_index: int = 1,
        timestamp: float = 0.0,
    ) -> Session:
        """
        Create a new session with a unique ID.

        Args:
            episode_index: Initial episode number (default 1).
            timestamp: Initial playback timestamp in seconds.

        Returns:
            The newly created Session object.
        """
        session_id = uuid.uuid4().hex[:16]
        session = Session(
            session_id=session_id,
            episode_index=episode_index,
            timestamp=timestamp,
        )
        self._sessions[session_id] = session

        logger.info(
            "Session created: %s (episode=%d, timestamp=%.1f)",
            session_id,
            episode_index,
            timestamp,
        )
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Retrieve a session by ID. Returns None if not found or expired."""
        session = self._sessions.get(session_id)
        if session is None:
            return None

        # Check TTL inline
        if (time.time() - session.last_active) > self._ttl_seconds:
            del self._sessions[session_id]
            logger.info("Session %s expired on access", session_id)
            return None

        return session

    def update_session(
        self,
        session_id: str,
        episode_index: int | None = None,
        timestamp: float | None = None,
        rolling_context: str | None = None,
    ) -> Session | None:
        """
        Update fields on an existing session. Only provided fields
        are changed; None values are skipped.

        Returns the updated Session or None if not found.
        """
        session = self.get_session(session_id)
        if session is None:
            return None

        if episode_index is not None:
            session.episode_index = episode_index
        if timestamp is not None:
            session.timestamp = timestamp
        if rolling_context is not None:
            session.rolling_context = rolling_context

        session.touch()

        logger.debug(
            "Session updated: %s (episode=%d, ts=%.1f, ctx_len=%d)",
            session_id,
            session.episode_index,
            session.timestamp,
            len(session.rolling_context),
        )
        return session

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session by ID.

        Returns True if the session was found and deleted, False otherwise.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("Session deleted: %s", session_id)
            return True
        return False

    # ── Introspection ──

    @property
    def active_count(self) -> int:
        """Number of currently active (non-expired) sessions."""
        return len(self._sessions)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions as serialized dicts."""
        return [session.to_dict() for session in self._sessions.values()]

"""Tests for the Session Management endpoints and SessionManager service."""

from fastapi.testclient import TestClient

from app.main import app
from app.services.session_manager import Session, SessionManager

client = TestClient(app)


# ═══════════════════════════════════════════════
# SessionManager Unit Tests
# ═══════════════════════════════════════════════


class TestSessionManager:
    """Unit tests for the SessionManager service."""

    def setup_method(self):
        """Create a fresh SessionManager for each test."""
        self.sm = SessionManager(ttl_seconds=60)

    def test_create_session(self):
        """Creating a session returns a valid Session object."""
        session = self.sm.create_session(episode_index=3, timestamp=42.5)
        assert isinstance(session, Session)
        assert session.episode_index == 3
        assert session.timestamp == 42.5
        assert session.is_active is True
        assert len(session.session_id) == 16

    def test_get_session(self):
        """Retrieving a session by ID returns the same session."""
        session = self.sm.create_session()
        retrieved = self.sm.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_nonexistent_session(self):
        """Getting a non-existent session returns None."""
        result = self.sm.get_session("nonexistent")
        assert result is None

    def test_update_session_partial(self):
        """Updating only some fields leaves others unchanged."""
        session = self.sm.create_session(episode_index=1, timestamp=10.0)
        updated = self.sm.update_session(
            session.session_id,
            episode_index=5,
        )
        assert updated is not None
        assert updated.episode_index == 5
        assert updated.timestamp == 10.0  # unchanged

    def test_update_session_rolling_context(self):
        """Rolling context can be updated."""
        session = self.sm.create_session()
        ctx = "The statues began to move..."
        updated = self.sm.update_session(
            session.session_id,
            rolling_context=ctx,
        )
        assert updated is not None
        assert updated.rolling_context == ctx

    def test_update_nonexistent_session(self):
        """Updating a non-existent session returns None."""
        result = self.sm.update_session("nonexistent", episode_index=1)
        assert result is None

    def test_delete_session(self):
        """Deleting a session removes it from the store."""
        session = self.sm.create_session()
        deleted = self.sm.delete_session(session.session_id)
        assert deleted is True
        assert self.sm.get_session(session.session_id) is None

    def test_delete_nonexistent_session(self):
        """Deleting a non-existent session returns False."""
        assert self.sm.delete_session("nonexistent") is False

    def test_active_count(self):
        """Active count reflects the number of live sessions."""
        assert self.sm.active_count == 0
        self.sm.create_session()
        self.sm.create_session()
        assert self.sm.active_count == 2

    def test_list_sessions(self):
        """Listing sessions returns serialized session dicts."""
        self.sm.create_session()
        self.sm.create_session()
        sessions = self.sm.list_sessions()
        assert len(sessions) == 2
        assert "session_id" in sessions[0]

    def test_ttl_expiry_on_access(self):
        """A session that exceeds TTL should be purged on access."""
        sm = SessionManager(ttl_seconds=0)  # immediate expiry
        session = sm.create_session()
        import time
        time.sleep(0.01)
        result = sm.get_session(session.session_id)
        assert result is None

    def test_session_to_dict(self):
        """Session.to_dict() returns all expected fields."""
        session = self.sm.create_session(episode_index=2, timestamp=100.0)
        d = session.to_dict()
        assert d["session_id"] == session.session_id
        assert d["episode_index"] == 2
        assert d["timestamp"] == 100.0
        assert d["is_active"] is True
        assert "created_at" in d
        assert "last_active" in d
        assert "rolling_context_length" in d


# ═══════════════════════════════════════════════
# Session REST Endpoint Integration Tests
# ═══════════════════════════════════════════════


def test_create_session_endpoint():
    """POST /api/session creates a session and returns its state."""
    response = client.post(
        "/api/session",
        json={"episode_index": 3, "timestamp": 55.0},
    )
    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data
    assert data["episode_index"] == 3
    assert data["timestamp"] == 55.0
    assert data["is_active"] is True


def test_create_session_defaults():
    """POST /api/session with no body uses defaults."""
    response = client.post("/api/session", json={})
    assert response.status_code == 201
    data = response.json()
    assert data["episode_index"] == 1
    assert data["timestamp"] == 0.0


def test_get_session_endpoint():
    """GET /api/session/{id} retrieves a created session."""
    # Create first
    create_resp = client.post("/api/session", json={"episode_index": 2})
    session_id = create_resp.json()["session_id"]

    # Get
    get_resp = client.get(f"/api/session/{session_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["session_id"] == session_id
    assert data["episode_index"] == 2


def test_get_session_not_found():
    """GET /api/session/{id} returns 404 for unknown session."""
    response = client.get("/api/session/does_not_exist")
    assert response.status_code == 404


def test_update_session_endpoint():
    """PATCH /api/session/{id} updates session fields."""
    # Create
    create_resp = client.post(
        "/api/session", json={"episode_index": 1, "timestamp": 0.0}
    )
    session_id = create_resp.json()["session_id"]

    # Update
    patch_resp = client.patch(
        f"/api/session/{session_id}",
        json={"episode_index": 5, "timestamp": 300.0},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["episode_index"] == 5
    assert data["timestamp"] == 300.0


def test_update_session_not_found():
    """PATCH /api/session/{id} returns 404 for unknown session."""
    response = client.patch(
        "/api/session/does_not_exist",
        json={"episode_index": 2},
    )
    assert response.status_code == 404


def test_delete_session_endpoint():
    """DELETE /api/session/{id} removes the session."""
    # Create
    create_resp = client.post("/api/session", json={})
    session_id = create_resp.json()["session_id"]

    # Delete
    del_resp = client.delete(f"/api/session/{session_id}")
    assert del_resp.status_code == 204

    # Confirm gone
    get_resp = client.get(f"/api/session/{session_id}")
    assert get_resp.status_code == 404


def test_delete_session_not_found():
    """DELETE /api/session/{id} returns 404 for unknown session."""
    response = client.delete("/api/session/does_not_exist")
    assert response.status_code == 404


def test_create_session_invalid_episode():
    """Episode index of 0 or negative should be rejected."""
    response = client.post(
        "/api/session",
        json={"episode_index": 0, "timestamp": 0.0},
    )
    assert response.status_code == 422

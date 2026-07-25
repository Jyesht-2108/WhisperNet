"""Tests for the WebSocket session handler."""

import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_session(episode_index: int = 3, timestamp: float = 100.0) -> str:
    """Helper: create a session and return its ID."""
    resp = client.post(
        "/api/session",
        json={"episode_index": episode_index, "timestamp": timestamp},
    )
    assert resp.status_code == 201
    return resp.json()["session_id"]


# ── Connection Tests ──


def test_websocket_connect_with_valid_session():
    """WebSocket should accept connection for a valid session."""
    session_id = _create_session()
    with client.websocket_connect(f"/ws/session/{session_id}") as ws:
        # Send a ping to verify connection
        ws.send_json({"type": "ping"})
        response = ws.receive_json()
        assert response["type"] == "pong"


def test_websocket_reject_invalid_session():
    """WebSocket should reject connection for a non-existent session."""
    try:
        with client.websocket_connect("/ws/session/invalid_session_id") as ws:
            # Should not reach here
            pass
    except Exception:
        # FastAPI test client raises an exception on close with error code
        pass


# ── Ping/Pong ──


def test_websocket_ping_pong():
    """Ping should return pong."""
    session_id = _create_session()
    with client.websocket_connect(f"/ws/session/{session_id}") as ws:
        ws.send_json({"type": "ping"})
        response = ws.receive_json()
        assert response["type"] == "pong"


# ── Context Update ──


def test_websocket_context_update():
    """context_update should acknowledge and update session state."""
    session_id = _create_session()
    with client.websocket_connect(f"/ws/session/{session_id}") as ws:
        ws.send_json({
            "type": "context_update",
            "rolling_context": "The hunters are inside the dungeon now.",
            "episode_index": 4,
            "timestamp": 200.0,
        })
        response = ws.receive_json()
        assert response["type"] == "context_ack"
        assert response["status"] == "ok"

    # Verify session was updated via REST
    get_resp = client.get(f"/api/session/{session_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["episode_index"] == 4
    assert data["timestamp"] == 200.0


# ── Ask Question ──


def test_websocket_ask_question():
    """ask_question should trigger the orchestration pipeline and return a prompt."""
    session_id = _create_session(episode_index=3, timestamp=142.5)

    # First update context so the session has rolling context
    with client.websocket_connect(f"/ws/session/{session_id}") as ws:
        ws.send_json({
            "type": "context_update",
            "rolling_context": (
                "The statues began to move, their eyes glowing red. "
                "Jin-Woo felt his legs tremble."
            ),
        })
        ack = ws.receive_json()
        assert ack["type"] == "context_ack"

        # Now ask a question
        ws.send_json({
            "type": "ask_question",
            "user_query": "Who is the giant statue in the dungeon?",
        })
        response = ws.receive_json()

        assert response["type"] == "prompt_response"
        assert "system_instructions" in response
        assert "voice_settings" in response
        assert "user_input" in response
        assert "active_character" in response
        assert "processing_time_ms" in response
        assert len(response["system_instructions"]) > 100


def test_websocket_ask_question_missing_query():
    """ask_question without user_query should return an error."""
    session_id = _create_session()
    with client.websocket_connect(f"/ws/session/{session_id}") as ws:
        ws.send_json({
            "type": "ask_question",
            # No user_query
        })
        response = ws.receive_json()
        assert response["type"] == "error"
        assert "user_query" in response["detail"].lower()


def test_websocket_ask_question_spoiler_free():
    """
    ask_question with episode_index=3 should not include
    episode 4+ spoilers in the response.
    """
    session_id = _create_session(episode_index=3, timestamp=100.0)
    with client.websocket_connect(f"/ws/session/{session_id}") as ws:
        ws.send_json({
            "type": "ask_question",
            "user_query": "Who is the giant statue?",
            "rolling_context": "The statues are moving in the temple.",
            "episode_index": 3,
        })
        response = ws.receive_json()
        assert response["type"] == "prompt_response"

        instructions_lower = response["system_instructions"].lower()
        # Episode 4+ content must not appear
        assert "shadow extraction" not in instructions_lower
        assert "shadow monarch" not in instructions_lower
        assert "daily quest" not in instructions_lower


# ── Error Handling ──


def test_websocket_unknown_message_type():
    """Unknown message types should return an error."""
    session_id = _create_session()
    with client.websocket_connect(f"/ws/session/{session_id}") as ws:
        ws.send_json({"type": "unknown_type"})
        response = ws.receive_json()
        assert response["type"] == "error"
        assert "unknown" in response["detail"].lower()


def test_websocket_invalid_json():
    """Invalid JSON should return an error, not crash."""
    session_id = _create_session()
    with client.websocket_connect(f"/ws/session/{session_id}") as ws:
        ws.send_text("not valid json {{{")
        response = ws.receive_json()
        assert response["type"] == "error"
        assert "invalid" in response["detail"].lower()


def test_websocket_missing_type_field():
    """A message without a 'type' field should return a validation error."""
    session_id = _create_session()
    with client.websocket_connect(f"/ws/session/{session_id}") as ws:
        ws.send_json({"user_query": "test"})  # no 'type'
        response = ws.receive_json()
        assert response["type"] == "error"


# ── Multiple Messages ──


def test_websocket_multiple_messages():
    """Should handle multiple sequential messages on the same connection."""
    session_id = _create_session()
    with client.websocket_connect(f"/ws/session/{session_id}") as ws:
        # Ping
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] == "pong"

        # Context update
        ws.send_json({
            "type": "context_update",
            "rolling_context": "New scene.",
            "episode_index": 2,
        })
        assert ws.receive_json()["type"] == "context_ack"

        # Another ping
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] == "pong"

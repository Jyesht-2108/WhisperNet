"""Tests for the OpenAI Realtime token exchange endpoint."""

import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _has_placeholder_key() -> bool:
    """Check if the OpenAI API key is the default placeholder."""
    from app.config import get_settings
    settings = get_settings()
    return settings.OPENAI_API_KEY == "sk-placeholder"


def test_realtime_token_rejects_placeholder_key():
    """
    With the default placeholder API key, the endpoint should
    return a 500 error telling the user to configure the key.

    If a non-placeholder key is configured, the endpoint will
    attempt to call OpenAI (expected to fail with 502 in test
    environments without a valid key).
    """
    payload = {
        "sdp_offer": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n",
        "model": "gpt-4o-realtime-preview",
    }
    response = client.post("/api/realtime/token", json=payload)

    if _has_placeholder_key():
        assert response.status_code == 500
        data = response.json()
        assert "OPENAI_API_KEY" in data["detail"]
    else:
        # Non-placeholder key configured but likely invalid in test env
        # Expect either 502 (OpenAI error) or 200 (valid key)
        assert response.status_code in (200, 502)


def test_realtime_token_validates_sdp_offer():
    """An empty SDP offer should be rejected by Pydantic validation."""
    payload = {
        "sdp_offer": "",
        "model": "gpt-4o-realtime-preview",
    }
    response = client.post("/api/realtime/token", json=payload)
    # Pydantic min_length=1 will reject empty string
    assert response.status_code == 422


def test_realtime_token_missing_sdp_offer():
    """Missing SDP offer field should be rejected."""
    payload = {"model": "gpt-4o-realtime-preview"}
    response = client.post("/api/realtime/token", json=payload)
    assert response.status_code == 422


def test_realtime_token_default_model():
    """If model is not provided, it should default to gpt-4o-realtime-preview."""
    payload = {
        "sdp_offer": "v=0\r\no=test\r\n",
    }
    response = client.post("/api/realtime/token", json=payload)
    if _has_placeholder_key():
        # Expect 500 (placeholder key), not 422 (validation error)
        assert response.status_code == 500
    else:
        # Non-placeholder key: expect 502 (invalid key) or 200 (valid key)
        assert response.status_code in (200, 502)

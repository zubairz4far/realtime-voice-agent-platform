from __future__ import annotations

import time

import pytest

from server.app.auth import SessionTokenError, issue_session_token, verify_session_token

KEY = "k" * 32


def test_session_token_round_trip():
    token, expires_at = issue_session_token(KEY, "session-1", 60)
    assert expires_at > int(time.time())
    assert verify_session_token(KEY, token) == "session-1"


def test_tampered_session_token_rejected():
    token, _ = issue_session_token(KEY, "session-1", 60)
    with pytest.raises(SessionTokenError, match="invalid_session_token"):
        verify_session_token(KEY, token[:-1] + ("0" if token[-1] != "0" else "1"))


def test_short_signing_key_rejected():
    with pytest.raises(SessionTokenError, match="session_signing_key_too_short"):
        issue_session_token("short", "session-1", 60)

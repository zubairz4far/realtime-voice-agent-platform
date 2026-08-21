from __future__ import annotations

import hashlib
import hmac
import secrets
import time


class SessionTokenError(ValueError):
    pass


def issue_session_token(signing_key: str, session_id: str, ttl_seconds: int) -> tuple[str, int]:
    if len(signing_key.encode()) < 32:
        raise SessionTokenError("session_signing_key_too_short")
    if ttl_seconds < 60 or ttl_seconds > 24 * 60 * 60:
        raise SessionTokenError("invalid_session_ttl")
    expires_at = int(time.time()) + ttl_seconds
    payload = f"{session_id}.{expires_at}"
    signature = hmac.new(signing_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"v1.{payload}.{signature}", expires_at


def verify_session_token(signing_key: str, token: str) -> str:
    try:
        version, session_id, expires_raw, signature = token.split(".", 3)
        expires_at = int(expires_raw)
    except (ValueError, AttributeError) as exc:
        raise SessionTokenError("malformed_session_token") from exc
    if version != "v1" or not session_id:
        raise SessionTokenError("malformed_session_token")
    if expires_at < int(time.time()):
        raise SessionTokenError("expired_session_token")
    payload = f"{session_id}.{expires_at}"
    expected = hmac.new(signing_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not secrets.compare_digest(signature, expected):
        raise SessionTokenError("invalid_session_token")
    return session_id

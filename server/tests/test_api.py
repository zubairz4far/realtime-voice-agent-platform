from __future__ import annotations

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def bootstrap() -> dict:
    response = client.post("/v1/realtime/bootstrap")
    assert response.status_code == 200
    return response.json()


def auth_headers(session: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {session['session_token']}"}


def test_health_ready_in_demo_mode():
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["demo_mode"] is True


def test_bootstrap_returns_ephemeral_and_backend_tokens():
    data = bootstrap()
    assert data["realtime_client_secret"] == "demo_ephemeral_key"
    assert data["realtime_model"] == "gpt-realtime-2.1"
    assert data["session_id"]
    assert data["session_token"].startswith("v1.")


def test_tool_endpoint_requires_session_token():
    response = client.post(
        "/v1/tools/execute",
        json={"call_id": "c1", "name": "lookup_order", "arguments": {"order_id": "ORD-100001"}},
    )
    assert response.status_code == 401


def test_tool_endpoint_and_replay():
    session = bootstrap()
    payload = {
        "call_id": "voice-tool-call-1",
        "name": "schedule_callback",
        "arguments": {"customer_id": "CUS-100001", "preferred_window": "morning"},
    }
    first = client.post("/v1/tools/execute", headers=auth_headers(session), json=payload)
    second = client.post("/v1/tools/execute", headers=auth_headers(session), json=payload)
    assert first.status_code == 200
    assert first.json()["ok"] is True
    assert second.json()["replayed"] is True
    assert second.json()["result"] == first.json()["result"]


def test_latency_summary_records_interruption_and_turn_latency():
    session = bootstrap()
    headers = auth_headers(session)
    first = client.post(
        "/v1/telemetry/event",
        headers=headers,
        json={"event": "user_speech_stopped", "client_monotonic_ms": 500},
    )
    assert first.status_code == 200
    client.post(
        "/v1/telemetry/event",
        headers=headers,
        json={"event": "assistant_audio_started", "client_monotonic_ms": 725},
    )
    client.post(
        "/v1/telemetry/event",
        headers=headers,
        json={"event": "assistant_interrupted", "client_monotonic_ms": 800},
    )
    summary = client.get("/v1/telemetry/summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["turn_latencies_ms"] == [225.0]
    assert summary.json()["interruptions"] == 1

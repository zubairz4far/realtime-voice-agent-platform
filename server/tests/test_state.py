from __future__ import annotations

from server.app.models import LatencyEvent
from server.app.state import SessionRegistry, SlidingWindowLimiter


def test_turn_latency_measured_from_user_stop_to_assistant_start():
    registry = SessionRegistry()
    registry.record_event(
        "s1", LatencyEvent(event="user_speech_stopped", client_monotonic_ms=1000)
    )
    summary = registry.record_event(
        "s1", LatencyEvent(event="assistant_audio_started", client_monotonic_ms=1325)
    )
    assert summary.turn_latencies_ms == [325.0]
    assert summary.mean_turn_latency_ms == 325.0


def test_interruption_counted():
    registry = SessionRegistry()
    summary = registry.record_event(
        "s1", LatencyEvent(event="assistant_interrupted", client_monotonic_ms=50)
    )
    assert summary.interruptions == 1


def test_rate_limiter_blocks_after_limit():
    limiter = SlidingWindowLimiter(2, window_seconds=60)
    assert limiter.allow("s1") is True
    assert limiter.allow("s1") is True
    assert limiter.allow("s1") is False

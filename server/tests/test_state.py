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
    assert summary.turn_samples == 1
    assert summary.mean_turn_latency_ms == 325.0
    assert summary.p50_turn_latency_ms == 325.0
    assert summary.p95_turn_latency_ms == 325.0


def test_latency_percentiles_are_reported_for_multiple_turns():
    registry = SessionRegistry()
    latencies = [200, 250, 300, 350, 400]
    for index, latency in enumerate(latencies):
        stop = float(index * 1000)
        registry.record_event(
            "s1", LatencyEvent(event="user_speech_stopped", client_monotonic_ms=stop)
        )
        summary = registry.record_event(
            "s1",
            LatencyEvent(
                event="assistant_audio_started",
                client_monotonic_ms=stop + latency,
            ),
        )

    assert summary.turn_samples == 5
    assert summary.mean_turn_latency_ms == 300.0
    assert summary.p50_turn_latency_ms == 300.0
    assert summary.p95_turn_latency_ms == 390.0


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

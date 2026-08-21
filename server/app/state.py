from __future__ import annotations

import statistics
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from time import monotonic

from server.app.models import LatencyEvent, SessionSummary, ToolCallResponse


@dataclass
class SessionState:
    events: list[LatencyEvent] = field(default_factory=list)
    interruptions: int = 0
    tool_calls: int = 0
    completed_tool_calls: int = 0
    tool_results: dict[str, ToolCallResponse] = field(default_factory=dict)
    pending_user_stop_ms: float | None = None
    turn_latencies_ms: list[float] = field(default_factory=list)


class SessionRegistry:
    def __init__(self) -> None:
        self._states: dict[str, SessionState] = {}
        self._lock = threading.RLock()

    def ensure(self, session_id: str) -> SessionState:
        with self._lock:
            return self._states.setdefault(session_id, SessionState())

    def record_event(self, session_id: str, event: LatencyEvent) -> SessionSummary:
        with self._lock:
            state = self.ensure(session_id)
            state.events.append(event)
            if event.event == "assistant_interrupted":
                state.interruptions += 1
            elif event.event == "user_speech_stopped":
                state.pending_user_stop_ms = event.client_monotonic_ms
            elif event.event == "assistant_audio_started" and state.pending_user_stop_ms is not None:
                delta = event.client_monotonic_ms - state.pending_user_stop_ms
                if 0 <= delta <= 60_000:
                    state.turn_latencies_ms.append(delta)
                state.pending_user_stop_ms = None
            elif event.event == "tool_started":
                state.tool_calls += 1
            elif event.event == "tool_completed":
                state.completed_tool_calls += 1
            return self.summary(session_id)

    def get_tool_result(self, session_id: str, call_id: str) -> ToolCallResponse | None:
        with self._lock:
            return self.ensure(session_id).tool_results.get(call_id)

    def store_tool_result(self, session_id: str, response: ToolCallResponse) -> None:
        with self._lock:
            self.ensure(session_id).tool_results[response.call_id] = response

    def summary(self, session_id: str) -> SessionSummary:
        with self._lock:
            state = self.ensure(session_id)
            mean = statistics.fmean(state.turn_latencies_ms) if state.turn_latencies_ms else None
            return SessionSummary(
                session_id=session_id,
                events=len(state.events),
                interruptions=state.interruptions,
                tool_calls=state.tool_calls,
                completed_tool_calls=state.completed_tool_calls,
                turn_latencies_ms=list(state.turn_latencies_ms),
                mean_turn_latency_ms=mean,
            )


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

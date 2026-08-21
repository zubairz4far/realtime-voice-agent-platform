from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SessionBootstrap(BaseModel):
    session_id: str
    session_token: str
    session_token_expires_at: int
    realtime_client_secret: str
    realtime_model: str
    demo_mode: bool = False


class ToolCallRequest(BaseModel):
    call_id: str = Field(min_length=1, max_length=160)
    name: Literal["lookup_order", "schedule_callback"]
    arguments: dict[str, Any]


class ToolCallResponse(BaseModel):
    call_id: str
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    replayed: bool = False


class LatencyEvent(BaseModel):
    event: Literal[
        "session_connected",
        "user_speech_started",
        "user_speech_stopped",
        "assistant_audio_started",
        "assistant_audio_stopped",
        "assistant_interrupted",
        "tool_started",
        "tool_completed",
    ]
    client_monotonic_ms: float = Field(ge=0)
    call_id: str | None = Field(default=None, max_length=160)


class SessionSummary(BaseModel):
    session_id: str
    events: int
    interruptions: int
    tool_calls: int
    completed_tool_calls: int
    turn_latencies_ms: list[float]
    mean_turn_latency_ms: float | None

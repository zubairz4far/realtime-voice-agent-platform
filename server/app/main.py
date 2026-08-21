from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server.app.auth import SessionTokenError, issue_session_token, verify_session_token
from server.app.config import Settings
from server.app.models import LatencyEvent, SessionBootstrap, SessionSummary, ToolCallRequest, ToolCallResponse
from server.app.realtime import RealtimeCredentialError, create_realtime_client_secret
from server.app.state import SessionRegistry, SlidingWindowLimiter
from server.app.tools import ToolExecutor

settings = Settings.from_env()
registry = SessionRegistry()
limiter = SlidingWindowLimiter(settings.max_tool_calls_per_minute)
bootstrap_limiter = SlidingWindowLimiter(10)
tools = ToolExecutor()
app = FastAPI(title="Realtime Voice Agent Platform", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["authorization", "content-type"],
)


def _session_from_auth(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="session_token_required")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return verify_session_token(settings.session_signing_key, token)
    except SessionTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    signing_ready = len(settings.session_signing_key.encode()) >= 32
    provider_ready = settings.demo_mode or bool(settings.openai_api_key)
    ready = signing_ready and provider_ready
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "session_signing": signing_ready,
            "realtime_provider": provider_ready,
            "demo_mode": settings.demo_mode,
            "model": settings.realtime_model,
        },
    )


@app.post("/v1/realtime/bootstrap", response_model=SessionBootstrap)
async def bootstrap(request: Request) -> SessionBootstrap:
    client_key = request.client.host if request.client else "unknown"
    if not bootstrap_limiter.allow(client_key):
        raise HTTPException(status_code=429, detail="bootstrap_rate_limit_exceeded")
    session_id = secrets.token_urlsafe(18)
    try:
        session_token, expires_at = issue_session_token(
            settings.session_signing_key,
            session_id,
            settings.session_ttl_seconds,
        )
    except SessionTokenError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        secret = await create_realtime_client_secret(settings)
    except RealtimeCredentialError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    registry.ensure(session_id)
    return SessionBootstrap(
        session_id=session_id,
        session_token=session_token,
        session_token_expires_at=expires_at,
        realtime_client_secret=secret["value"],
        realtime_model=settings.realtime_model,
        demo_mode=settings.demo_mode,
    )


@app.post("/v1/tools/execute", response_model=ToolCallResponse)
def execute_tool(
    payload: ToolCallRequest,
    session_id: str = Depends(_session_from_auth),
) -> ToolCallResponse:
    if not limiter.allow(session_id):
        raise HTTPException(status_code=429, detail="tool_rate_limit_exceeded")

    previous = registry.get_tool_result(session_id, payload.call_id)
    if previous is not None:
        replay = previous.model_copy(update={"replayed": True})
        return replay

    registry.record_event(
        session_id,
        LatencyEvent(event="tool_started", client_monotonic_ms=0, call_id=payload.call_id),
    )
    result = tools.execute(payload.call_id, payload.name, payload.arguments)
    registry.store_tool_result(session_id, result)
    registry.record_event(
        session_id,
        LatencyEvent(event="tool_completed", client_monotonic_ms=0, call_id=payload.call_id),
    )
    return result


@app.post("/v1/telemetry/event", response_model=SessionSummary)
def record_latency_event(
    payload: LatencyEvent,
    session_id: str = Depends(_session_from_auth),
) -> SessionSummary:
    return registry.record_event(session_id, payload)


@app.get("/v1/telemetry/summary", response_model=SessionSummary)
def telemetry_summary(session_id: str = Depends(_session_from_auth)) -> SessionSummary:
    return registry.summary(session_id)


_STATIC_DIR = Path(__file__).resolve().parents[2] / "client" / "dist"
if _STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="client")

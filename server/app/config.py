from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_base_url: str
    realtime_model: str
    session_signing_key: str
    session_ttl_seconds: int
    max_tool_calls_per_minute: int
    demo_mode: bool
    allowed_origins: tuple[str, ...]

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            realtime_model=os.getenv("REALTIME_MODEL", "gpt-realtime-2.1").strip(),
            session_signing_key=os.getenv("VOICE_SESSION_SIGNING_KEY", "").strip(),
            session_ttl_seconds=int(os.getenv("VOICE_SESSION_TTL_SECONDS", "3600")),
            max_tool_calls_per_minute=int(os.getenv("MAX_TOOL_CALLS_PER_MINUTE", "30")),
            demo_mode=os.getenv("DEMO_MODE", "false").lower() in {"1", "true", "yes"},
            allowed_origins=tuple(
                item.strip()
                for item in os.getenv(
                    "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
                ).split(",")
                if item.strip()
            ),
        )

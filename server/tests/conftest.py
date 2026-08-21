from __future__ import annotations

import os

os.environ.setdefault("VOICE_SESSION_SIGNING_KEY", "test-signing-key-that-is-at-least-32-bytes")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("MAX_TOOL_CALLS_PER_MINUTE", "100")

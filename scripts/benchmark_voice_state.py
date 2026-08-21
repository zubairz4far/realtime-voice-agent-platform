from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app.models import LatencyEvent
from server.app.state import SessionRegistry
from server.app.tools import ToolExecutor


def main() -> int:
    registry = SessionRegistry()
    session_id = "benchmark-session"
    latencies = [180, 220, 260, 310, 340, 400, 460, 520, 610, 720]

    cases: dict[str, bool] = {}
    for idx, latency in enumerate(latencies):
        stop = 1_000.0 + idx * 2_000
        registry.record_event(
            session_id,
            LatencyEvent(event="user_speech_stopped", client_monotonic_ms=stop),
        )
        summary = registry.record_event(
            session_id,
            LatencyEvent(
                event="assistant_audio_started",
                client_monotonic_ms=stop + latency,
            ),
        )
        cases[f"turn_latency_{idx}_exact"] = summary.turn_latencies_ms[-1] == float(latency)

    for idx in range(3):
        registry.record_event(
            session_id,
            LatencyEvent(event="assistant_interrupted", client_monotonic_ms=50_000 + idx),
        )
    cases["interruptions_counted"] = registry.summary(session_id).interruptions == 3

    executor = ToolExecutor()
    known = executor.execute("lookup-1", "lookup_order", {"order_id": "ORD-100001"})
    cases["known_order_lookup"] = bool(known.ok and known.result and known.result["found"])

    invalid = executor.execute("lookup-2", "lookup_order", {"order_id": "../../etc/passwd"})
    cases["invalid_order_rejected"] = invalid.error == "invalid_tool_arguments"

    args = {"customer_id": "CUS-100001", "preferred_window": "afternoon"}
    first = executor.execute("callback-1", "schedule_callback", args)
    replay = executor.execute("callback-1", "schedule_callback", args)
    cases["callback_created"] = bool(first.ok and first.result)
    cases["callback_replay_idempotent"] = bool(
        replay.ok and replay.replayed and replay.result == first.result
    )

    invalid_window = executor.execute(
        "callback-2",
        "schedule_callback",
        {"customer_id": "CUS-100001", "preferred_window": "03:00"},
    )
    cases["invalid_callback_window_rejected"] = invalid_window.error == "invalid_tool_arguments"

    sorted_latencies = sorted(latencies)
    p95_index = max(0, round(0.95 * len(sorted_latencies) + 0.5) - 1)
    summary = {
        "suite": "voice_state_v1",
        "cases": len(cases),
        "passed": sum(cases.values()),
        "failed": [name for name, ok in cases.items() if not ok],
        "unsafe_tool_accepts": sum(
            1
            for name in ("invalid_order_rejected", "invalid_callback_window_rejected")
            if not cases[name]
        ),
        "latency_fixture": {
            "turns": len(latencies),
            "mean_ms": statistics.fmean(latencies),
            "median_ms": statistics.median(latencies),
            "p95_ms": sorted_latencies[p95_index],
            "note": "synthetic state-machine fixture; not live provider/network latency",
        },
    }
    print(json.dumps(summary, indent=2))
    return 1 if summary["failed"] or summary["unsafe_tool_accepts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

# Controlled Live WebRTC Latency Benchmark

This protocol measures **user speech stop -> first assistant audio** for the browser Realtime session.
It is intentionally separate from the deterministic state-machine fixture in `scripts/benchmark_voice_state.py`.

## Measurement

- start event: `input_audio_buffer.speech_stopped` -> `user_speech_stopped`
- end event: Realtime SDK `audio_start` -> `assistant_audio_started`
- clock: browser `performance.now()` captured at event receipt
- delivery: telemetry is serialized after timestamp capture so HTTP request reordering cannot change event order
- outputs: raw turn samples, mean, p50, p95, interruption count
- percentile method: linear interpolation over sorted samples

## Controlled run

1. Use one browser/device and one stable network connection for the entire run.
2. Close competing audio/video workloads and keep the microphone position fixed.
3. Start the backend with `DEMO_MODE=false` and a server-only `OPENAI_API_KEY`.
4. Connect the browser once and do not reconnect during the run.
5. Complete at least **20 normal voice turns** before exporting results. Avoid tool calls in the latency-only run so tool execution does not confound the speech latency measurement.
6. Use short, similar prompts (roughly one sentence) and wait for the assistant to begin speaking before the next turn.
7. After >=20 measured turns, click **Export benchmark JSON**.
8. Preserve the raw JSON alongside the commit SHA, browser version, OS, approximate network type, and test date.

## Suggested utterance set

Repeat this 10-prompt set twice for a 20-turn minimum:

1. “Give me one sentence about reliable software.”
2. “Name one benefit of low latency.”
3. “Explain WebRTC in one sentence.”
4. “What is a rate limit?”
5. “Define idempotency briefly.”
6. “What does p95 latency mean?”
7. “Give one example of a secure API boundary.”
8. “What is voice activity detection?”
9. “Why are short-lived credentials useful?”
10. “Summarize this conversation in one sentence.”

## Reporting

Report the result as live evidence only when the JSON contains at least 20 measured turns. Keep synthetic fixture numbers explicitly labeled as synthetic.

Recommended portfolio wording:

> Controlled live WebRTC benchmark, N=<turn_samples>: p50 <p50> ms, p95 <p95> ms from detected user speech-stop to first assistant-audio event. Raw samples and test protocol preserved with the benchmark artifact.

Do not compare runs across different networks/devices as if they were directly equivalent unless the environment is documented.

# Realtime Voice Agent Platform

**v0.1.0** — a production-oriented browser voice-agent foundation built around low-latency WebRTC speech-to-speech, interruption handling, secure backend tools, and explicit latency/state evaluation.

This project is intentionally different from a basic speech-to-text chatbot: the browser runs a live Realtime session while all consequential backend tools remain behind a separate signed server authorization boundary.

## Architecture

```text
Browser microphone
      |
      | WebRTC audio
      v
RealtimeSession / GPT-Realtime
      |
      | automatic VAD + interruption
      | function-tool request
      v
Browser tool adapter
      |
      | signed backend session token
      v
FastAPI tool gateway
      |
      +--> exact tool allowlist
      +--> strict Pydantic arguments
      +--> per-session rate limit
      +--> idempotent side effects
      |
      v
bounded structured result
      |
      v
Realtime conversation

Parallel path:
transport/audio events -> latency registry -> turn latency + interruption summary
```

## Current implementation

### Realtime browser client

- OpenAI Agents SDK `0.17.0`
- browser WebRTC transport
- current default model: `gpt-realtime-2.1`
- semantic VAD with high eagerness
- automatic interruption event handling
- manual Stop Agent control using `session.interrupt()`
- microphone mute/unmute
- optional typed messages in the same live session
- conversation-history rendering
- assistant audio start/stop instrumentation
- raw speech-start/speech-stop transport instrumentation

### Credential boundary

The browser never receives `OPENAI_API_KEY`.

`POST /v1/realtime/bootstrap` creates:

1. a short-lived Realtime client secret via the provider's GA `/v1/realtime/client_secrets` endpoint, and
2. a separate HMAC-SHA256 backend session token used only for this application's tool/telemetry APIs.

The two credentials have different purposes. A Realtime credential does not automatically authorize application tools.

### Backend tools

Two deterministic portfolio tools are included:

- `lookup_order(order_id)` — read-only lookup with strict `ORD-######` validation
- `schedule_callback(customer_id, preferred_window)` — side-effect simulation with strict arguments and call-ID idempotency

The backend rejects tool names outside the allowlist and invalid arguments. Tool execution is rate-limited per signed session.

## Evaluation

The project separates **state-machine evidence** from future **live provider/network latency**.

### Verified GitHub Actions evidence

Verified on GitHub Actions for the v0.1 implementation:

- **15/15 Python tests passed**
- deterministic voice-state/security benchmark: **16/16 passed**
- deterministic benchmark: **0 unsafe tool accepts**
- Ruff: **passed**
- TypeScript type-check + Vite production build: **passed**
- Docker multi-stage production image build: **passed**

The frontend gate compiled the pinned Agents SDK/TypeScript/Vite stack and produced a production bundle successfully. Vite reported a non-blocking chunk-size optimization warning for the main bundle; it did not fail the build.

The synthetic latency fixture checks exact event accounting across 10 turns:

- mean: **402 ms**
- median: **370 ms**
- p95 fixture value: **720 ms**

These values are deliberately labeled as **synthetic state-machine fixtures**. They prove the measurement logic records the expected values; they are not claims about GPT-Realtime or internet latency.

No paid live Realtime request is used by the regression suite or CI.

Run the deterministic gates locally:

```bash
python -m pytest -q
python scripts/benchmark_voice_state.py
```

## CI gates

GitHub Actions independently verifies:

1. Ruff
2. Python tests
3. deterministic voice-state/security benchmark
4. TypeScript/Vite production build
5. Docker image build

No live paid Realtime request is required by CI.

## Local development

### Backend

```bash
cp .env.example .env
pip install -e ".[dev]"
uvicorn server.app.main:app --reload --port 8000
```

For zero-cost backend validation keep:

```env
DEMO_MODE=true
```

### Frontend

```bash
cd client
npm install
npm run dev
```

Set this when the frontend is running separately from FastAPI:

```env
VITE_API_BASE_URL=http://localhost:8000
```

### Live WebRTC mode

Configure server-only secrets:

```env
DEMO_MODE=false
OPENAI_API_KEY=...
VOICE_SESSION_SIGNING_KEY=<at-least-32-random-bytes>
REALTIME_MODEL=gpt-realtime-2.1
```

Then connect through the browser UI. A fresh short-lived client secret is minted at bootstrap time; do not place the normal provider key in frontend environment variables.

## Docker

```bash
docker build -t realtime-voice-agent-platform .
docker run --rm -p 8000:8000 --env-file .env realtime-voice-agent-platform
```

The Docker build compiles the Vite client, installs the Python service, serves the built frontend from FastAPI, runs as a non-root user, and includes a liveness healthcheck.

## API

- `GET /health/live`
- `GET /health/ready`
- `POST /v1/realtime/bootstrap`
- `POST /v1/tools/execute`
- `POST /v1/telemetry/event`
- `GET /v1/telemetry/summary`

## Why this belongs in the portfolio

It demonstrates a different engineering problem from text agents/RAG:

- realtime media transport
- browser/server credential separation
- voice turn-taking and barge-in handling
- tool security in a live session
- idempotent side effects
- event-driven latency instrumentation
- explicit distinction between synthetic measurement validation and live latency evidence

## Next milestones

1. run a controlled live WebRTC latency benchmark and record p50/p95 user-stop -> first-assistant-audio
2. add scripted Realtime SDK tests for interruption and tool-call workflows
3. add a server-side reasoning-agent delegation tool for complex requests
4. add SIP/Twilio telephony transport
5. move session/idempotency/rate-limit state to Redis for multi-replica deployment
6. add adversarial audio/noise/overlap evaluation

See [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) for trust boundaries and residual risks.

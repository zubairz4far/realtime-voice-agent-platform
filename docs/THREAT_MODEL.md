# Threat model — Realtime Voice Agent Platform v0.1

## Trust boundaries

1. Browser microphone/user input is untrusted.
2. The short-lived Realtime client secret is browser-visible by design; the long-lived provider key is server-only.
3. Model-selected tool names and arguments are untrusted until backend validation succeeds.
4. Backend tool results are data, not instructions.
5. Client telemetry is advisory measurement data and never an authorization input.

## Primary threats and controls

### Long-lived provider-key exposure

**Threat:** putting a normal API key in browser code exposes it to every client.

**Control:** the browser calls `/v1/realtime/bootstrap`; the backend mints a short-lived Realtime client secret using the server-held provider key. The normal provider key is never returned.

### Forged backend tool calls

**Threat:** a caller bypasses the voice model and calls the tool endpoint directly.

**Control:** bootstrap also issues a separate HMAC-SHA256 backend session token. Tool and telemetry APIs require this token and reject missing, expired, malformed, or invalid signatures.

### Tool argument smuggling

**Threat:** model or caller supplies malformed identifiers or arbitrary values.

**Control:** tool names are an exact allowlist and arguments are validated with Pydantic constraints before execution. Invalid order IDs and callback windows fail closed.

### Duplicate side effects

**Threat:** retries cause the same callback action multiple times.

**Control:** side-effecting callback creation is idempotent on `call_id`; a repeated call returns the stored result with `replayed=true`.

### Tool-call flood

**Threat:** a valid session repeatedly executes tools.

**Control:** per-session sliding-window tool rate limiting.

### Prompt injection in tool output

**Threat:** tool data contains text that tries to control the model.

**Control:** system instructions explicitly define tool output as data rather than instructions. v0.1 demo tools return bounded structured data. A future connector layer should add output schema validation/DLP for arbitrary external tools.

### Voice interruption/state mismatch

**Threat:** the agent continues talking after the user interrupts, causing stale conversation state.

**Control:** browser WebRTC uses Realtime interruption support; the UI also exposes manual `interrupt()`. Interruption events are recorded separately from turn-latency events.

### Telemetry spoofing

**Threat:** client-reported monotonic timestamps are manipulated.

**Control:** telemetry is operational evidence only. It does not authorize tool calls, issue credentials, or change policy. Production latency SLOs should also include trusted server/edge timestamps.

## Explicit residual risk

- v0.1 has not yet been measured against a live provider/network session in this repository artifact.
- browser-side Realtime behavior depends on the current Agents SDK and browser WebRTC implementation.
- the in-memory session registry, rate limiter, callback store, and idempotency records are single-instance controls.
- the demo tool store is not a production database.
- no telephony/SIP or Twilio bridge is included yet.
- no multi-agent handoff or separate reasoning-agent delegation is included yet.
- no voice-specific adversarial audio corpus has been run yet.

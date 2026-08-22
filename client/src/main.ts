import { RealtimeAgent, RealtimeSession, tool } from '@openai/agents/realtime';
import { z } from 'zod';
import {
  bindRealtimeWorkflowEvents,
  createBackendToolExecutor,
  type RealtimeEventSource,
} from './realtime_workflows';
import './style.css';

type Bootstrap = {
  session_id: string;
  session_token: string;
  session_token_expires_at: number;
  realtime_client_secret: string;
  realtime_model: string;
  demo_mode: boolean;
};

type Summary = {
  session_id: string;
  interruptions: number;
  turn_samples: number;
  turn_latencies_ms: number[];
  mean_turn_latency_ms: number | null;
  p50_turn_latency_ms: number | null;
  p95_turn_latency_ms: number | null;
};

const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? window.location.origin;
const statusEl = document.querySelector<HTMLElement>('#status')!;
const modelEl = document.querySelector<HTMLElement>('#model')!;
const latencyEl = document.querySelector<HTMLElement>('#latency')!;
const p50LatencyEl = document.querySelector<HTMLElement>('#p50-latency')!;
const p95LatencyEl = document.querySelector<HTMLElement>('#p95-latency')!;
const turnSamplesEl = document.querySelector<HTMLElement>('#turn-samples')!;
const interruptionsEl = document.querySelector<HTMLElement>('#interruptions')!;
const historyEl = document.querySelector<HTMLElement>('#history')!;
const connectButton = document.querySelector<HTMLButtonElement>('#connect')!;
const muteButton = document.querySelector<HTMLButtonElement>('#mute')!;
const interruptButton = document.querySelector<HTMLButtonElement>('#interrupt')!;
const disconnectButton = document.querySelector<HTMLButtonElement>('#disconnect')!;
const exportBenchmarkButton = document.querySelector<HTMLButtonElement>('#export-benchmark')!;
const textForm = document.querySelector<HTMLFormElement>('#text-form')!;
const textInput = document.querySelector<HTMLInputElement>('#text-input')!;

let bootstrap: Bootstrap | null = null;
let session: RealtimeSession | null = null;
let muted = false;
let latestSummary: Summary | null = null;
let telemetryQueue: Promise<void> = Promise.resolve();

async function backend<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('content-type', 'application/json');
  if (bootstrap) headers.set('authorization', `Bearer ${bootstrap.session_token}`);
  const response = await fetch(`${apiBase}${path}`, { ...init, headers });
  if (!response.ok) throw new Error(`${path} failed (${response.status})`);
  return response.json() as Promise<T>;
}

async function telemetry(
  event: string,
  callId?: string,
  clientMonotonicMs: number = performance.now(),
): Promise<void> {
  if (!bootstrap) return;
  try {
    const summary = await backend<Summary>('/v1/telemetry/event', {
      method: 'POST',
      body: JSON.stringify({
        event,
        client_monotonic_ms: clientMonotonicMs,
        call_id: callId ?? null,
      }),
    });
    latestSummary = summary;
    latencyEl.textContent = summary.mean_turn_latency_ms == null
      ? '—'
      : `${Math.round(summary.mean_turn_latency_ms)} ms`;
    p50LatencyEl.textContent = summary.p50_turn_latency_ms == null
      ? '—'
      : `${Math.round(summary.p50_turn_latency_ms)} ms`;
    p95LatencyEl.textContent = summary.p95_turn_latency_ms == null
      ? '—'
      : `${Math.round(summary.p95_turn_latency_ms)} ms`;
    turnSamplesEl.textContent = String(summary.turn_samples);
    interruptionsEl.textContent = String(summary.interruptions);
    exportBenchmarkButton.disabled = summary.turn_samples === 0;
  } catch (error) {
    console.warn('telemetry failed', error);
  }
}

function queueTelemetry(event: string, callId?: string): void {
  const capturedAt = performance.now();
  telemetryQueue = telemetryQueue.then(() => telemetry(event, callId, capturedAt));
}

const executeTool = createBackendToolExecutor(backend);

const lookupOrder = tool({
  name: 'lookup_order',
  description: 'Look up shipping status for an order after the user gives an order ID.',
  parameters: z.object({ order_id: z.string().regex(/^ORD-[0-9]{6}$/) }),
  async execute({ order_id }) {
    return executeTool('lookup_order', { order_id });
  },
});

const scheduleCallback = tool({
  name: 'schedule_callback',
  description: 'Schedule a support callback only after confirming customer ID and time window.',
  parameters: z.object({
    customer_id: z.string().regex(/^CUS-[0-9]{6}$/),
    preferred_window: z.enum(['morning', 'afternoon', 'evening']),
  }),
  async execute({ customer_id, preferred_window }) {
    return executeTool('schedule_callback', { customer_id, preferred_window });
  },
});

function renderHistory(items: unknown[]): void {
  const html = items.slice(-12).map((raw) => {
    const item = raw as Record<string, unknown>;
    const role = typeof item.role === 'string' ? item.role : String(item.type ?? 'event');
    let text = '';
    if (typeof item.transcript === 'string') text = item.transcript;
    else if (typeof item.text === 'string') text = item.text;
    else if (Array.isArray(item.content)) {
      text = item.content.map((part) => {
        const record = part as Record<string, unknown>;
        return String(record.transcript ?? record.text ?? '');
      }).filter(Boolean).join(' ');
    }
    if (!text) text = role.includes('tool') ? '[tool event]' : '[audio / event]';
    return `<div class="turn"><div class="role">${escapeHtml(role)}</div><div class="text">${escapeHtml(text)}</div></div>`;
  }).join('');
  historyEl.innerHTML = html || '<p class="muted">No turns yet.</p>';
  historyEl.scrollTop = historyEl.scrollHeight;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  })[char]!);
}

function setConnected(connected: boolean): void {
  connectButton.disabled = connected;
  muteButton.disabled = !connected;
  interruptButton.disabled = !connected;
  disconnectButton.disabled = !connected;
}

async function connect(): Promise<void> {
  statusEl.textContent = 'Bootstrapping…';
  await telemetryQueue;
  telemetryQueue = Promise.resolve();
  bootstrap = await backend<Bootstrap>('/v1/realtime/bootstrap', { method: 'POST', body: '{}' });
  latestSummary = null;
  latencyEl.textContent = '—';
  p50LatencyEl.textContent = '—';
  p95LatencyEl.textContent = '—';
  turnSamplesEl.textContent = '0';
  interruptionsEl.textContent = '0';
  exportBenchmarkButton.disabled = true;
  modelEl.textContent = bootstrap.realtime_model;

  if (bootstrap.demo_mode) {
    statusEl.textContent = 'Demo backend ready — live audio disabled';
    historyEl.innerHTML = '<p class="muted">Set DEMO_MODE=false and configure OPENAI_API_KEY for a live WebRTC session.</p>';
    return;
  }

  const agent = new RealtimeAgent({
    name: 'Voice Support Agent',
    instructions: 'Be concise. Use tools only when their required identifiers are confirmed. Never invent tool results.',
    tools: [lookupOrder, scheduleCallback],
  });

  session = new RealtimeSession(agent, {
    model: bootstrap.realtime_model,
    config: {
      outputModalities: ['audio'],
      parallelToolCalls: true,
      audio: {
        input: {
          turnDetection: { type: 'semantic_vad', eagerness: 'high' },
        },
      },
    },
  });

  bindRealtimeWorkflowEvents(session as unknown as RealtimeEventSource, {
    queueTelemetry,
    renderHistory,
    onError: (error) => {
      console.error(error);
      statusEl.textContent = 'Error';
    },
  });

  await session.connect({ apiKey: bootstrap.realtime_client_secret });
  await telemetry('session_connected');
  statusEl.textContent = 'Connected';
  setConnected(true);
}

connectButton.addEventListener('click', () => {
  void connect().catch((error) => {
    console.error(error);
    statusEl.textContent = 'Connection failed';
  });
});

muteButton.addEventListener('click', () => {
  if (!session) return;
  muted = !muted;
  session.mute(muted);
  muteButton.textContent = muted ? 'Unmute' : 'Mute';
});

interruptButton.addEventListener('click', () => session?.interrupt());

disconnectButton.addEventListener('click', () => {
  session?.close();
  session = null;
  statusEl.textContent = 'Disconnected';
  setConnected(false);
});

exportBenchmarkButton.addEventListener('click', () => {
  if (!bootstrap || !latestSummary || latestSummary.turn_samples === 0) return;
  const report = {
    benchmark: 'live_webrtc_user_stop_to_first_assistant_audio',
    captured_at: new Date().toISOString(),
    model: bootstrap.realtime_model,
    session_id: bootstrap.session_id,
    measurement: {
      start_event: 'user_speech_stopped',
      end_event: 'assistant_audio_started',
      clock: 'browser performance.now()',
      percentile_method: 'linear interpolation over sorted samples',
    },
    metrics: latestSummary,
  };
  const blob = new Blob([`${JSON.stringify(report, null, 2)}\n`], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `voice-latency-benchmark-${Date.now()}.json`;
  link.click();
  URL.revokeObjectURL(url);
});

textForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const value = textInput.value.trim();
  if (!value || !session) return;
  session.sendMessage(value);
  textInput.value = '';
});

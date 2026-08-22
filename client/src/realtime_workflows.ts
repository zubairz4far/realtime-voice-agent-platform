export type TelemetryEventName =
  | 'assistant_audio_started'
  | 'assistant_audio_stopped'
  | 'assistant_interrupted'
  | 'user_speech_started'
  | 'user_speech_stopped';

type EventHandler = (...args: unknown[]) => void;

export type RealtimeEventSource = {
  on: (event: string, handler: EventHandler) => unknown;
};

export type RealtimeWorkflowBindings = {
  queueTelemetry: (event: TelemetryEventName) => void;
  renderHistory: (history: unknown[]) => void;
  onError: (error: unknown) => void;
};

export function bindRealtimeWorkflowEvents(
  session: RealtimeEventSource,
  bindings: RealtimeWorkflowBindings,
): void {
  session.on('audio_start', () => bindings.queueTelemetry('assistant_audio_started'));
  session.on('audio_stopped', () => bindings.queueTelemetry('assistant_audio_stopped'));
  session.on('audio_interrupted', () => bindings.queueTelemetry('assistant_interrupted'));
  session.on('history_updated', (history) => bindings.renderHistory(history as unknown[]));
  session.on('transport_event', (event) => {
    const raw = event as Record<string, unknown>;
    if (raw.type === 'input_audio_buffer.speech_started') {
      bindings.queueTelemetry('user_speech_started');
    }
    if (raw.type === 'input_audio_buffer.speech_stopped') {
      bindings.queueTelemetry('user_speech_stopped');
    }
  });
  session.on('error', (error) => bindings.onError(error));
}

type ToolResponse = {
  ok: boolean;
  result?: Record<string, unknown>;
  error?: string;
};

type Backend = <T>(path: string, init?: RequestInit) => Promise<T>;

export function createBackendToolExecutor(
  backend: Backend,
  newCallId: () => string = () => crypto.randomUUID(),
): (name: string, args: Record<string, unknown>) => Promise<string> {
  return async (name, args) => {
    const callId = newCallId();
    const response = await backend<ToolResponse>('/v1/tools/execute', {
      method: 'POST',
      body: JSON.stringify({ call_id: callId, name, arguments: args }),
    });
    return JSON.stringify(response.ok ? response.result : { error: response.error });
  };
}

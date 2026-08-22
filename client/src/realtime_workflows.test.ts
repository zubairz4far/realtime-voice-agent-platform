import { describe, expect, it, vi } from 'vitest';

import {
  bindRealtimeWorkflowEvents,
  createBackendToolExecutor,
  type RealtimeEventSource,
} from './realtime_workflows';

class FakeSession implements RealtimeEventSource {
  private handlers = new Map<string, Array<(...args: unknown[]) => void>>();

  on(event: string, handler: (...args: unknown[]) => void): void {
    const current = this.handlers.get(event) ?? [];
    current.push(handler);
    this.handlers.set(event, current);
  }

  emit(event: string, ...args: unknown[]): void {
    for (const handler of this.handlers.get(event) ?? []) handler(...args);
  }
}

describe('Realtime SDK-facing workflow bindings', () => {
  it('records interruption and transport speech events', () => {
    const session = new FakeSession();
    const queueTelemetry = vi.fn();

    bindRealtimeWorkflowEvents(session, {
      queueTelemetry,
      renderHistory: vi.fn(),
      onError: vi.fn(),
    });

    session.emit('transport_event', { type: 'input_audio_buffer.speech_stopped' });
    session.emit('audio_interrupted');
    session.emit('audio_start');

    expect(queueTelemetry.mock.calls).toEqual([
      ['user_speech_stopped'],
      ['assistant_interrupted'],
      ['assistant_audio_started'],
    ]);
  });

  it('forwards history and SDK errors to application callbacks', () => {
    const session = new FakeSession();
    const renderHistory = vi.fn();
    const onError = vi.fn();

    bindRealtimeWorkflowEvents(session, {
      queueTelemetry: vi.fn(),
      renderHistory,
      onError,
    });

    const history = [{ role: 'assistant', text: 'hello' }];
    const error = new Error('transport failed');
    session.emit('history_updated', history);
    session.emit('error', error);

    expect(renderHistory).toHaveBeenCalledWith(history);
    expect(onError).toHaveBeenCalledWith(error);
  });
});

describe('backend tool workflow', () => {
  it('sends the exact tool name, arguments, and call id', async () => {
    const backend = vi.fn().mockResolvedValue({
      ok: true,
      result: { status: 'shipped' },
    });
    const executeTool = createBackendToolExecutor(backend, () => 'call-123');

    const result = await executeTool('lookup_order', { order_id: 'ORD-100001' });

    expect(result).toBe(JSON.stringify({ status: 'shipped' }));
    expect(backend).toHaveBeenCalledTimes(1);
    const [path, init] = backend.mock.calls[0];
    expect(path).toBe('/v1/tools/execute');
    expect(init).toMatchObject({ method: 'POST' });
    expect(JSON.parse(String(init.body))).toEqual({
      call_id: 'call-123',
      name: 'lookup_order',
      arguments: { order_id: 'ORD-100001' },
    });
  });

  it('returns a bounded error object when the backend rejects a tool call', async () => {
    const backend = vi.fn().mockResolvedValue({ ok: false, error: 'invalid arguments' });
    const executeTool = createBackendToolExecutor(backend, () => 'call-err');

    const result = await executeTool('schedule_callback', {
      customer_id: 'CUS-100001',
      preferred_window: 'morning',
    });

    expect(JSON.parse(result)).toEqual({ error: 'invalid arguments' });
  });
});

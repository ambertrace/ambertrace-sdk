/**
 * Tests for data models and serialization.
 */
import { serializeTrace, type Trace } from '../../src/models';

describe('serializeTrace', () => {
  const createFullTrace = (): Trace => ({
    trace_id: 'test-trace-id',
    timestamp: '2024-01-15T10:30:00.000Z',
    provider: 'openai',
    method: 'chat.completions.create',
    duration_ms: 150.5,
    request: {
      model: 'gpt-4',
      messages: [
        { role: 'user', content: 'Hello!' },
      ],
      parameters: { temperature: 0.7 },
    },
    response: {
      id: 'chatcmpl-123',
      model: 'gpt-4-0613',
      choices: [
        {
          index: 0,
          message: { role: 'assistant', content: 'Hi there!' },
          finish_reason: 'stop',
        },
      ],
      usage: {
        prompt_tokens: 10,
        completion_tokens: 5,
        total_tokens: 15,
      },
    },
    sdk_version: 'typescript/0.1.0',
    environment: 'test',
  });

  it('should serialize all fields correctly', () => {
    const trace = createFullTrace();
    const serialized = serializeTrace(trace);

    expect(serialized.trace_id).toBe('test-trace-id');
    expect(serialized.timestamp).toBe('2024-01-15T10:30:00.000Z');
    expect(serialized.provider).toBe('openai');
    expect(serialized.method).toBe('chat.completions.create');
    expect(serialized.duration_ms).toBe(150.5);
    expect(serialized.request).toEqual(trace.request);
    expect(serialized.response).toEqual(trace.response);
    expect(serialized.sdk_version).toBe('typescript/0.1.0');
    expect(serialized.environment).toBe('test');
  });

  it('should convert undefined response to null', () => {
    const trace: Trace = {
      ...createFullTrace(),
      response: undefined,
    };

    const serialized = serializeTrace(trace);

    expect(serialized.response).toBeNull();
  });

  it('should convert undefined error to null', () => {
    const trace = createFullTrace();

    const serialized = serializeTrace(trace);

    expect(serialized.error).toBeNull();
  });

  it('should convert undefined environment to null', () => {
    const trace: Trace = {
      ...createFullTrace(),
      environment: undefined,
    };

    const serialized = serializeTrace(trace);

    expect(serialized.environment).toBeNull();
  });

  it('should include error when present', () => {
    const trace: Trace = {
      ...createFullTrace(),
      response: undefined,
      error: {
        type: 'RateLimitError',
        message: 'Rate limit exceeded',
        code: '429',
      },
    };

    const serialized = serializeTrace(trace);

    expect(serialized.error).toEqual({
      type: 'RateLimitError',
      message: 'Rate limit exceeded',
      code: '429',
    });
    expect(serialized.response).toBeNull();
  });

  it('should return JSON-serializable object', () => {
    const trace = createFullTrace();
    const serialized = serializeTrace(trace);

    // Should not throw
    const json = JSON.stringify(serialized);
    const parsed = JSON.parse(json);

    expect(parsed.trace_id).toBe(trace.trace_id);
  });
});

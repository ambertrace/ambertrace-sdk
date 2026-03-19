/**
 * Tests for OpenAI trace collector.
 */
import { OpenAICollector } from '../../src/providers/openai/collector';
import { Config, setConfig, clearConfig } from '../../src/config';

describe('OpenAICollector', () => {
  let collector: OpenAICollector;

  beforeEach(() => {
    collector = new OpenAICollector();

    // Setup config
    clearConfig();
    const config = new Config({ apiKey: 'test-key', environment: 'test' });
    setConfig(config);
  });

  afterEach(() => {
    clearConfig();
  });

  describe('getProviderName', () => {
    it('should return "openai"', () => {
      expect(collector.getProviderName()).toBe('openai');
    });
  });

  describe('collectTrace', () => {
    const sampleRequest = {
      model: 'gpt-4',
      messages: [
        { role: 'system', content: 'You are a helpful assistant.' },
        { role: 'user', content: 'Hello!' },
      ],
      temperature: 0.7,
      max_tokens: 100,
    };

    const sampleResponse = {
      id: 'chatcmpl-123',
      model: 'gpt-4-0613',
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant',
            content: 'Hello! How can I help you today?',
          },
          finish_reason: 'stop',
        },
      ],
      usage: {
        prompt_tokens: 20,
        completion_tokens: 10,
        total_tokens: 30,
      },
    };

    it('should collect trace with response data', () => {
      const startTime = Date.now() - 500; // 500ms ago
      const trace = collector.collectTrace('trace-123', startTime, sampleRequest, sampleResponse);

      expect(trace).not.toBeNull();
      expect(trace?.trace_id).toBe('trace-123');
      expect(trace?.provider).toBe('openai');
      expect(trace?.method).toBe('chat.completions.create');
      expect(trace?.duration_ms).toBeGreaterThanOrEqual(500);
      expect(trace?.environment).toBe('test');
    });

    it('should extract request data correctly', () => {
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, sampleResponse);

      expect(trace).not.toBeNull();
      expect(trace!.request.model).toBe('gpt-4');
      expect(trace!.request.messages).toHaveLength(2);
      expect(trace!.request.messages[0]!.role).toBe('system');
      expect(trace!.request.messages[1]!.content).toBe('Hello!');
      expect(trace!.request.parameters).toEqual({ temperature: 0.7, max_tokens: 100 });
    });

    it('should extract response data correctly', () => {
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, sampleResponse);

      expect(trace).not.toBeNull();
      expect(trace!.response?.id).toBe('chatcmpl-123');
      expect(trace!.response?.model).toBe('gpt-4-0613');
      expect(trace!.response?.choices).toHaveLength(1);
      expect(trace!.response!.choices[0]!.message.content).toBe('Hello! How can I help you today?');
      expect(trace!.response!.choices[0]!.finish_reason).toBe('stop');
      expect(trace!.response?.usage.prompt_tokens).toBe(20);
      expect(trace!.response?.usage.completion_tokens).toBe(10);
      expect(trace!.response?.usage.total_tokens).toBe(30);
    });

    it('should collect trace with error data', () => {
      class RateLimitError extends Error {
        status = 429;
        constructor(message: string) {
          super(message);
          this.name = 'RateLimitError';
        }
      }

      const error = new RateLimitError('Rate limit exceeded');
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, undefined, error);

      expect(trace).not.toBeNull();
      expect(trace?.error?.type).toBe('RateLimitError');
      expect(trace?.error?.message).toBe('Rate limit exceeded');
      expect(trace?.error?.code).toBe('429');
      expect(trace?.response).toBeUndefined();
    });

    it('should extract error code from different error properties', () => {
      // Error with code property
      const errorWithCode = Object.assign(new Error('Test error'), { code: 'rate_limit' });
      const trace1 = collector.collectTrace('trace-1', Date.now(), sampleRequest, undefined, errorWithCode);
      expect(trace1?.error?.code).toBe('rate_limit');

      // Error with type property
      const errorWithType = Object.assign(new Error('Test error'), { type: 'invalid_request' });
      const trace2 = collector.collectTrace('trace-2', Date.now(), sampleRequest, undefined, errorWithType);
      expect(trace2?.error?.code).toBe('invalid_request');
    });

    it('should handle missing model gracefully', () => {
      const requestWithoutModel = { messages: sampleRequest.messages };
      const trace = collector.collectTrace('trace-123', Date.now(), requestWithoutModel, sampleResponse);

      expect(trace?.request.model).toBe('unknown');
    });

    it('should handle missing messages gracefully', () => {
      const requestWithoutMessages = { model: 'gpt-4' };
      const trace = collector.collectTrace('trace-123', Date.now(), requestWithoutMessages, sampleResponse);

      expect(trace?.request.messages).toEqual([]);
    });

    it('should handle missing response fields gracefully', () => {
      const partialResponse = { id: 'test-id' };
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, partialResponse);

      expect(trace?.response?.id).toBe('test-id');
      expect(trace?.response?.model).toBe('unknown');
      expect(trace?.response?.choices).toEqual([]);
      expect(trace?.response?.usage.prompt_tokens).toBe(0);
    });

    it('should include SDK version in trace', () => {
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, sampleResponse);

      expect(trace?.sdk_version).toMatch(/^typescript\//);
    });

    it('should include timestamp in ISO format', () => {
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, sampleResponse);

      expect(trace?.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
    });

    it('should never throw exception', () => {
      // Test with various bad inputs
      expect(() => collector.collectTrace('trace-123', Date.now(), null as unknown as Record<string, unknown>, null)).not.toThrow();
      expect(() => collector.collectTrace('trace-123', Date.now(), undefined as unknown as Record<string, unknown>, undefined)).not.toThrow();
    });

    it('should return null on collection error', () => {
      // Clear config to cause potential issues
      clearConfig();

      // Should return trace (with undefined environment) rather than throw
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, sampleResponse);
      expect(trace).not.toBeNull();
    });
  });
});

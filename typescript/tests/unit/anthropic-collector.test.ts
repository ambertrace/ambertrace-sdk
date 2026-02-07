/**
 * Tests for Anthropic trace collector.
 */
import { AnthropicCollector } from '../../src/providers/anthropic/collector';
import { Config, setConfig, clearConfig } from '../../src/config';

describe('AnthropicCollector', () => {
  let collector: AnthropicCollector;

  beforeEach(() => {
    collector = new AnthropicCollector();

    // Setup config
    clearConfig();
    const config = new Config({ apiKey: 'test-key', environment: 'test' });
    setConfig(config);
  });

  afterEach(() => {
    clearConfig();
  });

  describe('getProviderName', () => {
    it('should return "anthropic"', () => {
      expect(collector.getProviderName()).toBe('anthropic');
    });
  });

  describe('collectTrace', () => {
    const sampleRequest = {
      model: 'claude-3-opus-20240229',
      system: 'You are a helpful assistant.',
      messages: [{ role: 'user', content: 'Hello!' }],
      max_tokens: 1024,
      temperature: 0.7,
    };

    const sampleResponse = {
      id: 'msg_123',
      model: 'claude-3-opus-20240229',
      content: [{ type: 'text', text: 'Hello! How can I help you today?' }],
      stop_reason: 'end_turn',
      usage: {
        input_tokens: 20,
        output_tokens: 10,
      },
    };

    it('should collect trace with response data', () => {
      const startTime = Date.now() - 500; // 500ms ago
      const trace = collector.collectTrace('trace-123', startTime, sampleRequest, sampleResponse);

      expect(trace).not.toBeNull();
      expect(trace?.trace_id).toBe('trace-123');
      expect(trace?.provider).toBe('anthropic');
      expect(trace?.method).toBe('messages.create');
      expect(trace?.duration_ms).toBeGreaterThanOrEqual(500);
      expect(trace?.environment).toBe('test');
    });

    it('should prepend system message to messages list', () => {
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, sampleResponse);

      expect(trace).not.toBeNull();
      expect(trace!.request.messages).toHaveLength(2);
      expect(trace!.request.messages[0]!.role).toBe('system');
      expect(trace!.request.messages[0]!.content).toBe('You are a helpful assistant.');
      expect(trace!.request.messages[1]!.role).toBe('user');
      expect(trace!.request.messages[1]!.content).toBe('Hello!');
    });

    it('should handle request without system message', () => {
      const requestWithoutSystem = {
        model: 'claude-3-opus-20240229',
        messages: [{ role: 'user', content: 'Hello!' }],
        max_tokens: 1024,
      };

      const trace = collector.collectTrace('trace-123', Date.now(), requestWithoutSystem, sampleResponse);

      expect(trace).not.toBeNull();
      expect(trace!.request.messages).toHaveLength(1);
      expect(trace!.request.messages[0]!.role).toBe('user');
    });

    it('should normalize stop_reason to finish_reason', () => {
      // end_turn -> stop
      const trace1 = collector.collectTrace('trace-1', Date.now(), sampleRequest, {
        ...sampleResponse,
        stop_reason: 'end_turn',
      });
      expect(trace1).not.toBeNull();
      expect(trace1!.response!.choices[0]!.finish_reason).toBe('stop');

      // max_tokens -> length
      const trace2 = collector.collectTrace('trace-2', Date.now(), sampleRequest, {
        ...sampleResponse,
        stop_reason: 'max_tokens',
      });
      expect(trace2).not.toBeNull();
      expect(trace2!.response!.choices[0]!.finish_reason).toBe('length');

      // stop_sequence -> stop
      const trace3 = collector.collectTrace('trace-3', Date.now(), sampleRequest, {
        ...sampleResponse,
        stop_reason: 'stop_sequence',
      });
      expect(trace3).not.toBeNull();
      expect(trace3!.response!.choices[0]!.finish_reason).toBe('stop');

      // unknown reason passed through
      const trace4 = collector.collectTrace('trace-4', Date.now(), sampleRequest, {
        ...sampleResponse,
        stop_reason: 'some_other_reason',
      });
      expect(trace4).not.toBeNull();
      expect(trace4!.response!.choices[0]!.finish_reason).toBe('some_other_reason');
    });

    it('should normalize token fields', () => {
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, sampleResponse);

      // input_tokens -> prompt_tokens
      expect(trace?.response?.usage.prompt_tokens).toBe(20);
      // output_tokens -> completion_tokens
      expect(trace?.response?.usage.completion_tokens).toBe(10);
      // total calculated
      expect(trace?.response?.usage.total_tokens).toBe(30);
    });

    it('should flatten content blocks to string', () => {
      const responseWithMultipleBlocks = {
        ...sampleResponse,
        content: [
          { type: 'text', text: 'Hello! ' },
          { type: 'text', text: 'How can I help?' },
        ],
      };

      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, responseWithMultipleBlocks);

      expect(trace).not.toBeNull();
      expect(trace!.response!.choices[0]!.message.content).toBe('Hello! How can I help?');
    });

    it('should handle array content in request messages', () => {
      const requestWithArrayContent = {
        model: 'claude-3-opus-20240229',
        messages: [
          {
            role: 'user',
            content: [
              { type: 'text', text: 'First part. ' },
              { type: 'text', text: 'Second part.' },
            ],
          },
        ],
        max_tokens: 1024,
      };

      const trace = collector.collectTrace('trace-123', Date.now(), requestWithArrayContent, sampleResponse);

      expect(trace).not.toBeNull();
      expect(trace!.request.messages[0]!.content).toBe('First part.  Second part.');
    });

    it('should collect trace with error data', () => {
      class APIError extends Error {
        status_code = 429;
        constructor(message: string) {
          super(message);
          this.name = 'APIError';
        }
      }

      const error = new APIError('Rate limit exceeded');
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, undefined, error);

      expect(trace).not.toBeNull();
      expect(trace?.error?.type).toBe('APIError');
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
      const requestWithoutModel = { messages: sampleRequest.messages, max_tokens: 1024 };
      const trace = collector.collectTrace('trace-123', Date.now(), requestWithoutModel, sampleResponse);

      expect(trace?.request.model).toBe('unknown');
    });

    it('should handle missing messages gracefully', () => {
      const requestWithoutMessages = { model: 'claude-3-opus-20240229', max_tokens: 1024 };
      const trace = collector.collectTrace('trace-123', Date.now(), requestWithoutMessages, sampleResponse);

      expect(trace?.request.messages).toEqual([]);
    });

    it('should handle missing response fields gracefully', () => {
      const partialResponse = { id: 'test-id' };
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, partialResponse);

      expect(trace).not.toBeNull();
      expect(trace!.response?.id).toBe('test-id');
      expect(trace!.response?.model).toBe('unknown');
      expect(trace!.response!.choices[0]!.message.content).toBe('');
      expect(trace!.response?.usage.prompt_tokens).toBe(0);
    });

    it('should exclude system, model, messages from parameters', () => {
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, sampleResponse);

      expect(trace?.request.parameters).not.toHaveProperty('model');
      expect(trace?.request.parameters).not.toHaveProperty('messages');
      expect(trace?.request.parameters).not.toHaveProperty('system');
      expect(trace?.request.parameters).toHaveProperty('max_tokens');
      expect(trace?.request.parameters).toHaveProperty('temperature');
    });

    it('should include SDK version in trace', () => {
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, sampleResponse);

      expect(trace?.sdk_version).toMatch(/^ambertrace-node\//);
    });

    it('should include timestamp in ISO format', () => {
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, sampleResponse);

      expect(trace?.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
    });

    it('should never throw exception', () => {
      // Test with various bad inputs
      expect(() =>
        collector.collectTrace('trace-123', Date.now(), null as unknown as Record<string, unknown>, null)
      ).not.toThrow();
      expect(() =>
        collector.collectTrace('trace-123', Date.now(), undefined as unknown as Record<string, unknown>, undefined)
      ).not.toThrow();
    });
  });
});

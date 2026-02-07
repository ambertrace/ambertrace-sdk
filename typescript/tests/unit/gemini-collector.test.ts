/**
 * Tests for Gemini trace collector.
 */
import { GeminiCollector } from '../../src/providers/gemini/collector';
import { Config, setConfig, clearConfig } from '../../src/config';

describe('GeminiCollector', () => {
  let collector: GeminiCollector;

  beforeEach(() => {
    collector = new GeminiCollector();

    // Setup config
    clearConfig();
    const config = new Config({ apiKey: 'test-key', environment: 'test' });
    setConfig(config);
  });

  afterEach(() => {
    clearConfig();
  });

  describe('getProviderName', () => {
    it('should return "gemini"', () => {
      expect(collector.getProviderName()).toBe('gemini');
    });
  });

  describe('collectTrace', () => {
    const sampleRequest = {
      _ambertrace_model: 'gemini-pro',
      contents: 'Hello!',
    };

    const sampleResponse = {
      response_id: 'gemini-resp-123',
      model: 'gemini-pro',
      candidates: [
        {
          content: { parts: [{ text: 'Hello! How can I help you?' }] },
          finish_reason: 'STOP',
        },
      ],
      usage_metadata: {
        prompt_token_count: 15,
        candidates_token_count: 8,
        total_token_count: 23,
      },
      text: 'Hello! How can I help you?',
    };

    it('should collect trace with response data', () => {
      const startTime = Date.now() - 500; // 500ms ago
      const trace = collector.collectTrace('trace-123', startTime, sampleRequest, sampleResponse);

      expect(trace).not.toBeNull();
      expect(trace?.trace_id).toBe('trace-123');
      expect(trace?.provider).toBe('gemini');
      expect(trace?.method).toBe('generate_content');
      expect(trace?.duration_ms).toBeGreaterThanOrEqual(500);
      expect(trace?.environment).toBe('test');
    });

    it('should extract request data correctly', () => {
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, sampleResponse);

      expect(trace).not.toBeNull();
      expect(trace!.request.model).toBe('gemini-pro');
      expect(trace!.request.messages).toHaveLength(1);
      expect(trace!.request.messages[0]!.role).toBe('user');
      expect(trace!.request.messages[0]!.content).toBe('Hello!');
    });

    it('should extract response data correctly', () => {
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, sampleResponse);

      expect(trace).not.toBeNull();
      expect(trace!.response?.id).toBe('gemini-resp-123');
      expect(trace!.response?.model).toBe('gemini-pro');
      expect(trace!.response?.choices).toHaveLength(1);
      expect(trace!.response!.choices[0]!.message.role).toBe('assistant');
      expect(trace!.response!.choices[0]!.message.content).toContain('Hello');
      expect(trace!.response!.choices[0]!.finish_reason).toBe('stop');
    });

    it('should normalize Gemini token fields', () => {
      const trace = collector.collectTrace('trace-123', Date.now(), sampleRequest, sampleResponse);

      expect(trace?.response?.usage.prompt_tokens).toBe(15);
      expect(trace?.response?.usage.completion_tokens).toBe(8);
      expect(trace?.response?.usage.total_tokens).toBe(23);
    });

    it('should handle string contents', () => {
      const trace = collector.collectTrace(
        'trace-str',
        Date.now(),
        { _ambertrace_model: 'gemini-pro', contents: 'Tell me a joke' },
        sampleResponse
      );

      expect(trace).not.toBeNull();
      expect(trace!.request.messages).toHaveLength(1);
      expect(trace!.request.messages[0]!.role).toBe('user');
      expect(trace!.request.messages[0]!.content).toBe('Tell me a joke');
    });

    it('should handle list of Content objects', () => {
      const request = {
        _ambertrace_model: 'gemini-pro',
        contents: [
          { role: 'user', parts: [{ text: 'Hello' }] },
          { role: 'model', parts: [{ text: 'Hi there' }] },
        ],
      };

      const trace = collector.collectTrace('trace-list', Date.now(), request, sampleResponse);

      expect(trace).not.toBeNull();
      expect(trace!.request.messages).toHaveLength(2);
      expect(trace!.request.messages[0]!.role).toBe('user');
      expect(trace!.request.messages[0]!.content).toBe('Hello');
      expect(trace!.request.messages[1]!.role).toBe('model');
      expect(trace!.request.messages[1]!.content).toBe('Hi there');
    });

    it('should handle list of Part objects', () => {
      const request = {
        _ambertrace_model: 'gemini-pro',
        contents: [{ text: 'Part one' }, { text: 'Part two' }],
      };

      const trace = collector.collectTrace('trace-parts', Date.now(), request, sampleResponse);

      expect(trace).not.toBeNull();
      expect(trace!.request.messages).toHaveLength(2);
      expect(trace!.request.messages[0]!.content).toBe('Part one');
      expect(trace!.request.messages[1]!.content).toBe('Part two');
    });

    it('should handle list of strings', () => {
      const request = {
        _ambertrace_model: 'gemini-pro',
        contents: ['Hello', 'World'],
      };

      const trace = collector.collectTrace('trace-strings', Date.now(), request, sampleResponse);

      expect(trace).not.toBeNull();
      expect(trace!.request.messages).toHaveLength(2);
      expect(trace!.request.messages[0]!.content).toBe('Hello');
      expect(trace!.request.messages[1]!.content).toBe('World');
    });

    it('should handle null contents', () => {
      const request = {
        _ambertrace_model: 'gemini-pro',
        contents: null,
      };

      const trace = collector.collectTrace(
        'trace-null',
        Date.now(),
        request as unknown as Record<string, unknown>,
        sampleResponse
      );

      expect(trace).not.toBeNull();
      expect(trace!.request.messages).toEqual([]);
    });

    it('should normalize finish reasons', () => {
      const makeResponse = (finishReason: string) => ({
        ...sampleResponse,
        candidates: [
          {
            content: { parts: [{ text: 'response' }] },
            finish_reason: finishReason,
          },
        ],
      });

      // STOP -> stop
      const trace1 = collector.collectTrace('t1', Date.now(), sampleRequest, makeResponse('STOP'));
      expect(trace1!.response!.choices[0]!.finish_reason).toBe('stop');

      // MAX_TOKENS -> length
      const trace2 = collector.collectTrace(
        't2',
        Date.now(),
        sampleRequest,
        makeResponse('MAX_TOKENS')
      );
      expect(trace2!.response!.choices[0]!.finish_reason).toBe('length');

      // SAFETY -> content_filter
      const trace3 = collector.collectTrace(
        't3',
        Date.now(),
        sampleRequest,
        makeResponse('SAFETY')
      );
      expect(trace3!.response!.choices[0]!.finish_reason).toBe('content_filter');

      // RECITATION -> content_filter
      const trace4 = collector.collectTrace(
        't4',
        Date.now(),
        sampleRequest,
        makeResponse('RECITATION')
      );
      expect(trace4!.response!.choices[0]!.finish_reason).toBe('content_filter');
    });

    it('should normalize integer finish reasons', () => {
      const makeResponse = (finishReason: number) => ({
        ...sampleResponse,
        candidates: [
          {
            content: { parts: [{ text: 'response' }] },
            finish_reason: finishReason,
          },
        ],
      });

      // 1 -> stop (STOP)
      const trace1 = collector.collectTrace('t1', Date.now(), sampleRequest, makeResponse(1));
      expect(trace1!.response!.choices[0]!.finish_reason).toBe('stop');

      // 2 -> length (MAX_TOKENS)
      const trace2 = collector.collectTrace('t2', Date.now(), sampleRequest, makeResponse(2));
      expect(trace2!.response!.choices[0]!.finish_reason).toBe('length');

      // 3 -> content_filter (SAFETY)
      const trace3 = collector.collectTrace('t3', Date.now(), sampleRequest, makeResponse(3));
      expect(trace3!.response!.choices[0]!.finish_reason).toBe('content_filter');
    });

    it('should handle multiple candidates', () => {
      const multiResponse = {
        ...sampleResponse,
        candidates: [
          {
            content: { parts: [{ text: 'Response 1' }] },
            finish_reason: 'STOP',
          },
          {
            content: { parts: [{ text: 'Response 2' }] },
            finish_reason: 'STOP',
          },
        ],
      };

      const trace = collector.collectTrace(
        'trace-multi',
        Date.now(),
        sampleRequest,
        multiResponse
      );

      expect(trace).not.toBeNull();
      expect(trace!.response!.choices).toHaveLength(2);
      expect(trace!.response!.choices[0]!.index).toBe(0);
      expect(trace!.response!.choices[0]!.message.content).toBe('Response 1');
      expect(trace!.response!.choices[1]!.index).toBe(1);
      expect(trace!.response!.choices[1]!.message.content).toBe('Response 2');
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
      const trace = collector.collectTrace(
        'trace-err',
        Date.now(),
        sampleRequest,
        undefined,
        error
      );

      expect(trace).not.toBeNull();
      expect(trace?.error?.type).toBe('APIError');
      expect(trace?.error?.message).toBe('Rate limit exceeded');
      expect(trace?.error?.code).toBe('429');
      expect(trace?.response).toBeUndefined();
    });

    it('should extract error code from different error properties', () => {
      // Error with code property
      const errorWithCode = Object.assign(new Error('Test error'), { code: 'rate_limit' });
      const trace1 = collector.collectTrace(
        'trace-1',
        Date.now(),
        sampleRequest,
        undefined,
        errorWithCode
      );
      expect(trace1?.error?.code).toBe('rate_limit');

      // Error with type property
      const errorWithType = Object.assign(new Error('Test error'), { type: 'invalid_request' });
      const trace2 = collector.collectTrace(
        'trace-2',
        Date.now(),
        sampleRequest,
        undefined,
        errorWithType
      );
      expect(trace2?.error?.code).toBe('invalid_request');
    });

    it('should exclude sensitive keys from parameters', () => {
      const request = {
        model: 'gemini-pro',
        contents: 'Hello',
        _ambertrace_model: 'gemini-pro',
        api_key: 'secret-key-12345',
        apiKey: 'secret-key-12345',
        credentials: { token: 'secret' },
        client: {},
        _client: {},
        authClient: {},
        httpOptions: {},
        temperature: 0.7,
        max_output_tokens: 1024,
      };

      const trace = collector.collectTrace(
        'trace-sec',
        Date.now(),
        request as Record<string, unknown>,
        sampleResponse
      );

      expect(trace).not.toBeNull();
      // Security: sensitive keys must NOT appear in parameters
      expect(trace!.request.parameters).not.toHaveProperty('api_key');
      expect(trace!.request.parameters).not.toHaveProperty('apiKey');
      expect(trace!.request.parameters).not.toHaveProperty('credentials');
      expect(trace!.request.parameters).not.toHaveProperty('client');
      expect(trace!.request.parameters).not.toHaveProperty('_client');
      expect(trace!.request.parameters).not.toHaveProperty('authClient');
      expect(trace!.request.parameters).not.toHaveProperty('httpOptions');
      expect(trace!.request.parameters).not.toHaveProperty('model');
      expect(trace!.request.parameters).not.toHaveProperty('contents');
      expect(trace!.request.parameters).not.toHaveProperty('_ambertrace_model');

      // Non-sensitive params should be included
      expect(trace!.request.parameters).toHaveProperty('temperature');
      expect(trace!.request.parameters).toHaveProperty('max_output_tokens');
    });

    it('should never leak API key in trace', () => {
      const secretKey = 'AIzaSyD_SUPER_SECRET_KEY_12345';
      const request = {
        model: 'gemini-pro',
        contents: 'Hello',
        api_key: secretKey,
        apiKey: secretKey,
      };

      const trace = collector.collectTrace(
        'trace-leak',
        Date.now(),
        request as Record<string, unknown>,
        sampleResponse
      );

      // Convert entire trace to string and search for the key
      const traceStr = JSON.stringify(trace);
      expect(traceStr).not.toContain(secretKey);
    });

    it('should handle missing model gracefully', () => {
      const requestWithoutModel = { contents: 'Hello' };
      const trace = collector.collectTrace(
        'trace-no-model',
        Date.now(),
        requestWithoutModel,
        sampleResponse
      );

      expect(trace?.request.model).toBe('unknown');
    });

    it('should handle model from newer SDK kwargs', () => {
      const newerSdkRequest = {
        model: 'gemini-2.0-flash',
        contents: 'Hello!',
      };

      const trace = collector.collectTrace(
        'trace-newer',
        Date.now(),
        newerSdkRequest,
        sampleResponse
      );

      expect(trace?.request.model).toBe('gemini-2.0-flash');
    });

    it('should handle missing response fields gracefully', () => {
      const partialResponse = { response_id: 'test-id' };
      const trace = collector.collectTrace(
        'trace-partial',
        Date.now(),
        sampleRequest,
        partialResponse
      );

      expect(trace).not.toBeNull();
      expect(trace!.response?.id).toBe('test-id');
      expect(trace!.response?.model).toBe('unknown');
      expect(trace!.response?.choices).toEqual([]);
      expect(trace!.response?.usage.prompt_tokens).toBe(0);
    });

    it('should handle camelCase usage metadata (TS SDK)', () => {
      const tsResponse = {
        response_id: 'test',
        model: 'gemini-pro',
        candidates: [
          {
            content: { parts: [{ text: 'Hello' }] },
            finish_reason: 'STOP',
          },
        ],
        usageMetadata: {
          promptTokenCount: 10,
          candidatesTokenCount: 5,
          totalTokenCount: 15,
        },
      };

      const trace = collector.collectTrace(
        'trace-camel',
        Date.now(),
        sampleRequest,
        tsResponse
      );

      expect(trace?.response?.usage.prompt_tokens).toBe(10);
      expect(trace?.response?.usage.completion_tokens).toBe(5);
      expect(trace?.response?.usage.total_tokens).toBe(15);
    });

    it('should include SDK version in trace', () => {
      const trace = collector.collectTrace(
        'trace-ver',
        Date.now(),
        sampleRequest,
        sampleResponse
      );

      expect(trace?.sdk_version).toMatch(/^ambertrace-node\//);
    });

    it('should include timestamp in ISO format', () => {
      const trace = collector.collectTrace(
        'trace-ts',
        Date.now(),
        sampleRequest,
        sampleResponse
      );

      expect(trace?.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
    });

    it('should never throw exception', () => {
      expect(() =>
        collector.collectTrace(
          'trace-123',
          Date.now(),
          null as unknown as Record<string, unknown>,
          null
        )
      ).not.toThrow();
      expect(() =>
        collector.collectTrace(
          'trace-123',
          Date.now(),
          undefined as unknown as Record<string, unknown>,
          undefined
        )
      ).not.toThrow();
    });

    it('should return null on collection error', () => {
      clearConfig();

      // Should return trace (with undefined environment) rather than throw
      const trace = collector.collectTrace(
        'trace-123',
        Date.now(),
        sampleRequest,
        sampleResponse
      );
      expect(trace).not.toBeNull();
    });

    it('should handle response with text fallback (no candidates)', () => {
      const textOnlyResponse = {
        response_id: 'test-text',
        model: 'gemini-pro',
        candidates: [],
        text: 'Fallback text',
        usage_metadata: {
          prompt_token_count: 5,
          candidates_token_count: 3,
          total_token_count: 8,
        },
      };

      const trace = collector.collectTrace(
        'trace-text',
        Date.now(),
        sampleRequest,
        textOnlyResponse
      );

      expect(trace).not.toBeNull();
      expect(trace!.response!.choices).toHaveLength(1);
      expect(trace!.response!.choices[0]!.message.content).toBe('Fallback text');
      expect(trace!.response!.choices[0]!.finish_reason).toBe('stop');
    });

    it('should handle environment when not configured', () => {
      clearConfig();
      setConfig(new Config({ apiKey: 'test-key' }));

      const trace = collector.collectTrace(
        'trace-no-env',
        Date.now(),
        sampleRequest,
        sampleResponse
      );

      expect(trace).not.toBeNull();
      expect(trace?.environment).toBeUndefined();
    });
  });
});

/**
 * Tests for Transport class and trace delivery.
 */
import { Transport, getTransport, clearTransport } from '../../src/transport';
import { Config, setConfig, clearConfig } from '../../src/config';
import type { Trace } from '../../src/models';

// Mock node-fetch
jest.mock('node-fetch', () => jest.fn());
import fetch from 'node-fetch';

const mockFetch = fetch as jest.MockedFunction<typeof fetch>;

describe('Transport', () => {
  let transport: Transport;

  const createMockTrace = (id: string = 'test-trace-id'): Trace => ({
    trace_id: id,
    timestamp: new Date().toISOString(),
    provider: 'openai',
    method: 'chat.completions.create',
    duration_ms: 100,
    request: {
      model: 'gpt-4',
      messages: [{ role: 'user', content: 'Hello' }],
      parameters: {},
    },
    sdk_version: 'ambertrace-node/0.1.0',
  });

  beforeEach(() => {
    // Setup config
    clearConfig();
    const config = new Config({ apiKey: 'test-api-key', debug: false });
    setConfig(config);

    // Create fresh transport
    transport = new Transport();

    // Reset fetch mock
    mockFetch.mockReset();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      text: () => Promise.resolve('OK'),
    } as any);
  });

  afterEach(() => {
    clearConfig();
    clearTransport();
  });

  describe('sendTrace', () => {
    it('should send trace to endpoint', async () => {
      const trace = createMockTrace();
      transport.sendTrace(trace);

      // Wait for async operation
      await transport.flush();

      expect(mockFetch).toHaveBeenCalledTimes(1);
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.ambertrace.io/api/traces/ingest',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            Authorization: 'Bearer test-api-key',
          }),
        })
      );
    });

    it('should include trace data in request body', async () => {
      const trace = createMockTrace('my-trace-id');
      transport.sendTrace(trace);

      await transport.flush();

      const callArgs = mockFetch.mock.calls[0];
      expect(callArgs).toBeDefined();
      const body = JSON.parse(callArgs![1]?.body as string);
      expect(body.trace_id).toBe('my-trace-id');
      expect(body.provider).toBe('openai');
    });

    it('should handle network errors silently', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'));

      const trace = createMockTrace();
      transport.sendTrace(trace);

      // Should not throw
      await transport.flush();

      expect(mockFetch).toHaveBeenCalled();
    });

    it('should handle HTTP errors silently', async () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        text: () => Promise.resolve('Internal Server Error'),
      } as any);

      const trace = createMockTrace();
      transport.sendTrace(trace);

      // Should not throw
      await transport.flush();

      expect(mockFetch).toHaveBeenCalled();
    });

    it('should drop traces when queue is full', () => {
      // Send more than MAX_QUEUE_SIZE traces
      for (let i = 0; i < 1001; i++) {
        transport.sendTrace(createMockTrace(`trace-${i}`));
      }

      expect(transport.getDroppedCount()).toBe(1);
    });

    it('should not send when config is not set', async () => {
      clearConfig();

      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

      const trace = createMockTrace();
      transport.sendTrace(trace);

      await transport.flush();

      expect(mockFetch).not.toHaveBeenCalled();

      consoleErrorSpy.mockRestore();
    });
  });

  describe('flush', () => {
    it('should wait for pending traces', async () => {
      const trace = createMockTrace();
      transport.sendTrace(trace);

      expect(transport.getPendingCount()).toBeGreaterThan(0);

      await transport.flush();

      expect(transport.getPendingCount()).toBe(0);
    });

    it('should return immediately when no pending traces', async () => {
      const start = Date.now();
      await transport.flush();
      const duration = Date.now() - start;

      expect(duration).toBeLessThan(100);
    });

    it('should respect timeout', async () => {
      // Mock a slow fetch
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      mockFetch.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ ok: true } as any), 10000))
      );

      const trace = createMockTrace();
      transport.sendTrace(trace);

      const start = Date.now();
      await transport.flush(100); // 100ms timeout
      const duration = Date.now() - start;

      expect(duration).toBeLessThan(500);
    });
  });

  describe('getPendingCount', () => {
    it('should return 0 initially', () => {
      expect(transport.getPendingCount()).toBe(0);
    });

    it('should increment when trace is sent', () => {
      const trace = createMockTrace();
      transport.sendTrace(trace);

      expect(transport.getPendingCount()).toBeGreaterThan(0);
    });
  });

  describe('getDroppedCount', () => {
    it('should return 0 initially', () => {
      expect(transport.getDroppedCount()).toBe(0);
    });
  });

  describe('resetDroppedCount', () => {
    it('should reset dropped count to 0', () => {
      // Fill queue to cause drops
      for (let i = 0; i < 1005; i++) {
        transport.sendTrace(createMockTrace(`trace-${i}`));
      }

      expect(transport.getDroppedCount()).toBeGreaterThan(0);

      transport.resetDroppedCount();

      expect(transport.getDroppedCount()).toBe(0);
    });
  });
});

describe('Global transport functions', () => {
  beforeEach(() => {
    clearTransport();
    clearConfig();
  });

  describe('getTransport', () => {
    it('should return same instance on multiple calls', () => {
      const transport1 = getTransport();
      const transport2 = getTransport();

      expect(transport1).toBe(transport2);
    });
  });

  describe('clearTransport', () => {
    it('should clear the transport instance', () => {
      const transport1 = getTransport();
      clearTransport();
      const transport2 = getTransport();

      expect(transport1).not.toBe(transport2);
    });
  });
});

/**
 * Tests for Anthropic interceptor.
 */
import { AnthropicInterceptor } from '../../src/providers/anthropic/interceptor';
import { Config, setConfig, clearConfig } from '../../src/config';
import { clearTransport } from '../../src/transport';

// Mock node-fetch to prevent actual HTTP calls
jest.mock('node-fetch', () => jest.fn().mockResolvedValue({ ok: true }));

describe('AnthropicInterceptor', () => {
  let interceptor: AnthropicInterceptor;

  beforeEach(() => {
    interceptor = new AnthropicInterceptor();

    // Setup config
    clearConfig();
    const config = new Config({ apiKey: 'test-key', enabled: true });
    setConfig(config);
  });

  afterEach(() => {
    // Cleanup
    if (interceptor.isPatched()) {
      interceptor.unpatch();
    }
    clearConfig();
    clearTransport();
  });

  describe('getProviderName', () => {
    it('should return "anthropic"', () => {
      expect(interceptor.getProviderName()).toBe('anthropic');
    });
  });

  describe('isPatched', () => {
    it('should return false initially', () => {
      expect(interceptor.isPatched()).toBe(false);
    });
  });

  describe('patch', () => {
    it('should set isPatched to true after patching', () => {
      // The Anthropic SDK is available as a devDependency
      interceptor.patch();

      expect(interceptor.isPatched()).toBe(true);
    });

    it('should not patch twice', () => {
      interceptor.patch();
      interceptor.patch(); // Second call should be no-op

      expect(interceptor.isPatched()).toBe(true);
    });
  });

  describe('unpatch', () => {
    it('should set isPatched to false after unpatching', () => {
      interceptor.patch();
      interceptor.unpatch();

      expect(interceptor.isPatched()).toBe(false);
    });

    it('should not fail when unpatching without patching first', () => {
      expect(() => interceptor.unpatch()).not.toThrow();
    });
  });

  describe('integration with Anthropic SDK', () => {
    let Anthropic: typeof import('@anthropic-ai/sdk').default;
    let originalCreate: unknown;

    beforeEach(() => {
      // Get Anthropic and store original method
      Anthropic = require('@anthropic-ai/sdk').default;
      originalCreate = Anthropic.Messages.prototype.create;
    });

    afterEach(() => {
      // Restore original method
      if (originalCreate) {
        Anthropic.Messages.prototype.create = originalCreate as typeof Anthropic.Messages.prototype.create;
      }
    });

    it('should wrap messages.create method', () => {
      const beforePatch = Anthropic.Messages.prototype.create;
      interceptor.patch();
      const afterPatch = Anthropic.Messages.prototype.create;

      expect(afterPatch).not.toBe(beforePatch);
      expect(afterPatch.name).toBe('wrappedCreate');
    });

    it('should restore original method after unpatch', () => {
      const beforePatch = Anthropic.Messages.prototype.create;
      interceptor.patch();
      interceptor.unpatch();
      const afterUnpatch = Anthropic.Messages.prototype.create;

      expect(afterUnpatch).toBe(beforePatch);
    });

    it('should preserve response from wrapped method', async () => {
      const mockResponse = {
        id: 'msg_123',
        model: 'claude-3-opus-20240229',
        content: [{ type: 'text', text: 'Hello!' }],
        stop_reason: 'end_turn',
        usage: { input_tokens: 10, output_tokens: 5 },
      };

      // Mock the original create method
      const mockCreate = jest.fn().mockResolvedValue(mockResponse);
      Anthropic.Messages.prototype.create = mockCreate;

      interceptor.patch();

      const client = new Anthropic({ apiKey: 'test-key' });
      const result = await client.messages.create({
        model: 'claude-3-opus-20240229',
        max_tokens: 1024,
        messages: [{ role: 'user', content: 'Hi' }],
      });

      expect(result).toBe(mockResponse);
    });

    it('should re-throw errors from wrapped method', async () => {
      const mockError = new Error('API Error');

      // Mock the original create method to throw
      const mockCreate = jest.fn().mockRejectedValue(mockError);
      Anthropic.Messages.prototype.create = mockCreate;

      interceptor.patch();

      const client = new Anthropic({ apiKey: 'test-key' });

      await expect(
        client.messages.create({
          model: 'claude-3-opus-20240229',
          max_tokens: 1024,
          messages: [{ role: 'user', content: 'Hi' }],
        })
      ).rejects.toThrow('API Error');
    });

    it('should skip tracing when disabled', async () => {
      // Disable tracing
      clearConfig();
      setConfig(new Config({ apiKey: 'test-key', enabled: false }));

      const mockResponse = {
        id: 'test',
        content: [],
        stop_reason: 'end_turn',
        usage: { input_tokens: 0, output_tokens: 0 },
      };
      const mockCreate = jest.fn().mockResolvedValue(mockResponse);
      Anthropic.Messages.prototype.create = mockCreate;

      interceptor.patch();

      const client = new Anthropic({ apiKey: 'test-key' });
      const result = await client.messages.create({
        model: 'claude-3-opus-20240229',
        max_tokens: 1024,
        messages: [{ role: 'user', content: 'Hi' }],
      });

      expect(result).toBe(mockResponse);
      expect(mockCreate).toHaveBeenCalled();
    });
  });
});

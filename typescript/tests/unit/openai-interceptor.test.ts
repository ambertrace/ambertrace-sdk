/**
 * Tests for OpenAI interceptor.
 */
import { OpenAIInterceptor } from '../../src/providers/openai/interceptor';
import { Config, setConfig, clearConfig } from '../../src/config';
import { clearTransport } from '../../src/transport';

// Mock node-fetch to prevent actual HTTP calls
jest.mock('node-fetch', () => jest.fn().mockResolvedValue({ ok: true }));

describe('OpenAIInterceptor', () => {
  let interceptor: OpenAIInterceptor;

  beforeEach(() => {
    interceptor = new OpenAIInterceptor();

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
    it('should return "openai"', () => {
      expect(interceptor.getProviderName()).toBe('openai');
    });
  });

  describe('isPatched', () => {
    it('should return false initially', () => {
      expect(interceptor.isPatched()).toBe(false);
    });
  });

  describe('patch', () => {
    it('should set isPatched to true after patching', () => {
      // The OpenAI SDK is available as a devDependency
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

  describe('integration with OpenAI SDK', () => {
    let OpenAI: typeof import('openai').default;
    let originalCreate: unknown;

    beforeEach(() => {
      // Get OpenAI and store original method
      OpenAI = require('openai').default;
      originalCreate = OpenAI.Chat.Completions.prototype.create;
    });

    afterEach(() => {
      // Restore original method
      if (originalCreate) {
        OpenAI.Chat.Completions.prototype.create = originalCreate as typeof OpenAI.Chat.Completions.prototype.create;
      }
    });

    it('should wrap chat.completions.create method', () => {
      const beforePatch = OpenAI.Chat.Completions.prototype.create;
      interceptor.patch();
      const afterPatch = OpenAI.Chat.Completions.prototype.create;

      expect(afterPatch).not.toBe(beforePatch);
      expect(afterPatch.name).toBe('wrappedCreate');
    });

    it('should restore original method after unpatch', () => {
      const beforePatch = OpenAI.Chat.Completions.prototype.create;
      interceptor.patch();
      interceptor.unpatch();
      const afterUnpatch = OpenAI.Chat.Completions.prototype.create;

      expect(afterUnpatch).toBe(beforePatch);
    });

    it('should preserve response from wrapped method', async () => {
      const mockResponse = {
        id: 'chatcmpl-123',
        model: 'gpt-4',
        choices: [{ message: { role: 'assistant', content: 'Hello!' } }],
      };

      // Mock the original create method
      const mockCreate = jest.fn().mockResolvedValue(mockResponse);
      OpenAI.Chat.Completions.prototype.create = mockCreate;

      interceptor.patch();

      const client = new OpenAI({ apiKey: 'test-key' });
      const result = await client.chat.completions.create({
        model: 'gpt-4',
        messages: [{ role: 'user', content: 'Hi' }],
      });

      expect(result).toBe(mockResponse);
    });

    it('should re-throw errors from wrapped method', async () => {
      const mockError = new Error('API Error');

      // Mock the original create method to throw
      const mockCreate = jest.fn().mockRejectedValue(mockError);
      OpenAI.Chat.Completions.prototype.create = mockCreate;

      interceptor.patch();

      const client = new OpenAI({ apiKey: 'test-key' });

      await expect(
        client.chat.completions.create({
          model: 'gpt-4',
          messages: [{ role: 'user', content: 'Hi' }],
        })
      ).rejects.toThrow('API Error');
    });

    it('should skip tracing when disabled', async () => {
      // Disable tracing
      clearConfig();
      setConfig(new Config({ apiKey: 'test-key', enabled: false }));

      const mockResponse = { id: 'test', choices: [] };
      const mockCreate = jest.fn().mockResolvedValue(mockResponse);
      OpenAI.Chat.Completions.prototype.create = mockCreate;

      interceptor.patch();

      const client = new OpenAI({ apiKey: 'test-key' });
      const result = await client.chat.completions.create({
        model: 'gpt-4',
        messages: [{ role: 'user', content: 'Hi' }],
      });

      expect(result).toBe(mockResponse);
      expect(mockCreate).toHaveBeenCalled();
    });
  });
});

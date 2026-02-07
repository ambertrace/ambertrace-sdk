/**
 * Tests for Gemini interceptor.
 *
 * Uses the real @google/generative-ai SDK (installed as devDependency)
 * to test prototype patching, similar to the Anthropic interceptor tests.
 */
import { GeminiInterceptor } from '../../src/providers/gemini/interceptor';
import { Config, setConfig, clearConfig } from '../../src/config';
import { clearTransport } from '../../src/transport';

// Mock node-fetch to prevent actual HTTP calls
jest.mock('node-fetch', () => jest.fn().mockResolvedValue({ ok: true }));

describe('GeminiInterceptor', () => {
  let interceptor: GeminiInterceptor;

  beforeEach(() => {
    interceptor = new GeminiInterceptor();

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
    it('should return "gemini"', () => {
      expect(interceptor.getProviderName()).toBe('gemini');
    });
  });

  describe('isPatched', () => {
    it('should return false initially', () => {
      expect(interceptor.isPatched()).toBe(false);
    });
  });

  describe('unpatch', () => {
    it('should not fail when unpatching without patching first', () => {
      expect(() => interceptor.unpatch()).not.toThrow();
      expect(interceptor.isPatched()).toBe(false);
    });
  });

  describe('patch', () => {
    it('should set isPatched to true after patching', () => {
      interceptor.patch();

      expect(interceptor.isPatched()).toBe(true);
    });

    it('should not patch twice', () => {
      interceptor.patch();
      interceptor.patch(); // Second call should be no-op

      expect(interceptor.isPatched()).toBe(true);
    });
  });

  describe('integration with @google/generative-ai SDK', () => {
    let GenerativeModel: { prototype: Record<string, unknown> };
    let originalGenerateContent: unknown;

    beforeEach(() => {
      // Get the real GenerativeModel class from the SDK
      const genai = require('@google/generative-ai');
      GenerativeModel = genai.GenerativeModel;
      originalGenerateContent = GenerativeModel.prototype.generateContent;
    });

    afterEach(() => {
      // Restore original method
      if (originalGenerateContent) {
        GenerativeModel.prototype.generateContent = originalGenerateContent;
      }
    });

    it('should wrap generateContent method', () => {
      const beforePatch = GenerativeModel.prototype.generateContent;
      interceptor.patch();
      const afterPatch = GenerativeModel.prototype.generateContent;

      expect(afterPatch).not.toBe(beforePatch);
      expect((afterPatch as { name: string }).name).toBe('wrappedGenerateContent');
    });

    it('should restore original method after unpatch', () => {
      const beforePatch = GenerativeModel.prototype.generateContent;
      interceptor.patch();
      interceptor.unpatch();
      const afterUnpatch = GenerativeModel.prototype.generateContent;

      expect(afterUnpatch).toBe(beforePatch);
    });

    it('should preserve response from wrapped method', async () => {
      const mockResponse = {
        response_id: 'test-123',
        model: 'gemini-pro',
        candidates: [
          {
            content: { parts: [{ text: 'Hello!' }] },
            finish_reason: 'STOP',
          },
        ],
        usage_metadata: {
          prompt_token_count: 5,
          candidates_token_count: 3,
          total_token_count: 8,
        },
      };

      // Mock the original generateContent method
      const mockGenerateContent = jest.fn().mockResolvedValue(mockResponse);
      GenerativeModel.prototype.generateContent = mockGenerateContent;

      interceptor.patch();

      // Create mock instance
      const instance = Object.create(GenerativeModel.prototype);
      instance.model = 'gemini-pro';

      const result = await instance.generateContent('Hello!');

      expect(result).toBe(mockResponse);
    });

    it('should re-throw errors from wrapped method', async () => {
      const mockError = new Error('API Error');
      const mockGenerateContent = jest.fn().mockRejectedValue(mockError);
      GenerativeModel.prototype.generateContent = mockGenerateContent;

      interceptor.patch();

      const instance = Object.create(GenerativeModel.prototype);
      instance.model = 'gemini-pro';

      await expect(instance.generateContent('Hello!')).rejects.toThrow('API Error');
    });

    it('should skip tracing when disabled', async () => {
      clearConfig();
      setConfig(new Config({ apiKey: 'test-key', enabled: false }));

      const mockResponse = { id: 'test', candidates: [] };
      const mockGenerateContent = jest.fn().mockResolvedValue(mockResponse);
      GenerativeModel.prototype.generateContent = mockGenerateContent;

      interceptor.patch();

      const instance = Object.create(GenerativeModel.prototype);
      instance.model = 'gemini-pro';

      const result = await instance.generateContent('Hello!');

      expect(result).toBe(mockResponse);
      expect(mockGenerateContent).toHaveBeenCalled();
    });

    it('should handle synchronous responses', () => {
      const mockResponse = {
        response_id: 'sync-123',
        candidates: [],
        text: 'Sync response',
      };

      const mockGenerateContent = jest.fn().mockReturnValue(mockResponse);
      GenerativeModel.prototype.generateContent = mockGenerateContent;

      interceptor.patch();

      const instance = Object.create(GenerativeModel.prototype);
      instance.model = 'gemini-pro';

      const result = instance.generateContent('Hello!');

      expect(result).toBe(mockResponse);
    });

    it('should handle synchronous errors', () => {
      const mockError = new Error('Sync Error');
      const mockGenerateContent = jest.fn().mockImplementation(() => {
        throw mockError;
      });
      GenerativeModel.prototype.generateContent = mockGenerateContent;

      interceptor.patch();

      const instance = Object.create(GenerativeModel.prototype);
      instance.model = 'gemini-pro';

      expect(() => instance.generateContent('Hello!')).toThrow('Sync Error');
    });

    it('should not throw when trace collection fails', async () => {
      const mockResponse = {
        response_id: 'test-123',
        candidates: [],
        text: 'Hello!',
      };

      const mockGenerateContent = jest.fn().mockResolvedValue(mockResponse);
      GenerativeModel.prototype.generateContent = mockGenerateContent;

      interceptor.patch();

      const instance = Object.create(GenerativeModel.prototype);
      instance.model = 'gemini-pro';

      // Should not throw even if transport fails
      const result = await instance.generateContent('Hello!');
      expect(result).toBe(mockResponse);
    });
  });
});

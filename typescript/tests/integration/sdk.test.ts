/**
 * Integration tests for AmberTrace SDK.
 */
import ambertrace, {
  init,
  enable,
  disable,
  isEnabled,
  flush,
  shutdown,
  getVersion,
  VERSION,
} from '../../src/index';
import { getConfig, clearConfig } from '../../src/config';
import { clearTransport } from '../../src/transport';

// Mock node-fetch to prevent actual HTTP calls
jest.mock('node-fetch', () => jest.fn().mockResolvedValue({ ok: true }));

describe('AmberTrace SDK Integration', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    // Reset environment
    process.env = { ...originalEnv };
    delete process.env.AMBERTRACE_API_KEY;

    // Reset global state
    clearConfig();
    clearTransport();
  });

  afterEach(async () => {
    // Cleanup
    try {
      await shutdown();
    } catch {
      // Ignore errors during cleanup
    }
    process.env = originalEnv;
  });

  describe('init', () => {
    it('should initialize with API key', () => {
      init({ apiKey: 'test-api-key' });

      const config = getConfig();
      expect(config).not.toBeNull();
      expect(config?.apiKey).toBe('test-api-key');
    });

    it('should throw error when API key is missing', () => {
      expect(() => init()).toThrow('AmberTrace API key is required');
    });

    it('should accept all configuration options', () => {
      init({
        apiKey: 'test-key',
        baseUrl: 'https://custom.api.com',
        environment: 'production',
        debug: true,
        timeout: 10000,
        enabled: false,
      });

      const config = getConfig();
      expect(config?.baseUrl).toBe('https://custom.api.com');
      expect(config?.environment).toBe('production');
      expect(config?.debug).toBe(true);
      expect(config?.timeout).toBe(10000);
      expect(config?.enabled).toBe(false);
    });

    it('should enable tracing by default', () => {
      init({ apiKey: 'test-key' });

      expect(isEnabled()).toBe(true);
    });

    it('should not enable tracing when enabled is false', () => {
      init({ apiKey: 'test-key', enabled: false });

      expect(isEnabled()).toBe(false);
    });
  });

  describe('enable and disable', () => {
    beforeEach(() => {
      init({ apiKey: 'test-key', enabled: false });
    });

    it('should enable tracing', () => {
      expect(isEnabled()).toBe(false);

      enable();

      expect(isEnabled()).toBe(true);
    });

    it('should disable tracing', () => {
      enable();
      expect(isEnabled()).toBe(true);

      disable();

      expect(isEnabled()).toBe(false);
    });
  });

  describe('isEnabled', () => {
    it('should return false before initialization', () => {
      expect(isEnabled()).toBe(false);
    });

    it('should return true after init with enabled=true', () => {
      init({ apiKey: 'test-key', enabled: true });

      expect(isEnabled()).toBe(true);
    });
  });

  describe('flush', () => {
    it('should complete without error', async () => {
      init({ apiKey: 'test-key' });

      await expect(flush()).resolves.not.toThrow();
    });

    it('should accept timeout parameter', async () => {
      init({ apiKey: 'test-key' });

      await expect(flush(1000)).resolves.not.toThrow();
    });
  });

  describe('shutdown', () => {
    it('should disable tracing', async () => {
      init({ apiKey: 'test-key' });
      expect(isEnabled()).toBe(true);

      await shutdown();

      expect(isEnabled()).toBe(false);
    });

    it('should clear configuration', async () => {
      init({ apiKey: 'test-key' });
      expect(getConfig()).not.toBeNull();

      await shutdown();

      expect(getConfig()).toBeNull();
    });

    it('should complete without error even if not initialized', async () => {
      await expect(shutdown()).resolves.not.toThrow();
    });
  });

  describe('getVersion', () => {
    it('should return version string', () => {
      const version = getVersion();

      expect(typeof version).toBe('string');
      expect(version).toMatch(/^\d+\.\d+\.\d+/);
    });

    it('should match VERSION export', () => {
      expect(getVersion()).toBe(VERSION);
    });
  });

  describe('default export', () => {
    it('should expose all public functions', () => {
      expect(ambertrace.init).toBe(init);
      expect(ambertrace.enable).toBe(enable);
      expect(ambertrace.disable).toBe(disable);
      expect(ambertrace.isEnabled).toBe(isEnabled);
      expect(ambertrace.flush).toBe(flush);
      expect(ambertrace.shutdown).toBe(shutdown);
      expect(ambertrace.getVersion).toBe(getVersion);
      expect(ambertrace.VERSION).toBe(VERSION);
    });
  });

  describe('provider auto-detection', () => {
    it('should detect and register OpenAI when available', () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();

      init({ apiKey: 'test-key', debug: true });

      // Check that OpenAI was detected
      expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining('OpenAI SDK detected'));

      consoleSpy.mockRestore();
    });

    it('should detect and register Anthropic when available', () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();

      init({ apiKey: 'test-key', debug: true });

      // Check that Anthropic was detected
      expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining('Anthropic SDK detected'));

      consoleSpy.mockRestore();
    });

    it('should detect and register Gemini when available', () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();

      init({ apiKey: 'test-key', debug: true });

      // Check that Gemini was detected
      expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining('Gemini SDK detected'));

      consoleSpy.mockRestore();
    });
  });

  describe('end-to-end flow', () => {
    it('should complete full lifecycle', async () => {
      // Initialize
      init({ apiKey: 'test-key', environment: 'test' });
      expect(isEnabled()).toBe(true);

      // Disable
      disable();
      expect(isEnabled()).toBe(false);

      // Re-enable
      enable();
      expect(isEnabled()).toBe(true);

      // Flush (no traces to flush but should not error)
      await flush();

      // Shutdown
      await shutdown();
      expect(isEnabled()).toBe(false);
      expect(getConfig()).toBeNull();
    });
  });
});

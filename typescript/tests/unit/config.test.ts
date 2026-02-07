/**
 * Tests for Config class and configuration management.
 */
import { Config, setConfig, getConfig, clearConfig } from '../../src/config';

describe('Config', () => {
  // Store original env vars
  const originalEnv = process.env;

  beforeEach(() => {
    // Reset environment
    process.env = { ...originalEnv };
    delete process.env.AMBERTRACE_API_KEY;
    delete process.env.AMBERTRACE_BASE_URL;
    delete process.env.AMBERTRACE_ENVIRONMENT;
    delete process.env.AMBERTRACE_DEBUG;
    delete process.env.AMBERTRACE_TIMEOUT;
    delete process.env.AMBERTRACE_ENABLED;

    // Clear global config
    clearConfig();
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  describe('constructor', () => {
    it('should throw error when API key is missing', () => {
      expect(() => new Config()).toThrow('AmberTrace API key is required');
    });

    it('should accept API key from options', () => {
      const config = new Config({ apiKey: 'test-api-key' });
      expect(config.apiKey).toBe('test-api-key');
    });

    it('should accept API key from environment variable', () => {
      process.env.AMBERTRACE_API_KEY = 'env-api-key';
      const config = new Config();
      expect(config.apiKey).toBe('env-api-key');
    });

    it('should prefer options over environment variable for API key', () => {
      process.env.AMBERTRACE_API_KEY = 'env-api-key';
      const config = new Config({ apiKey: 'options-api-key' });
      expect(config.apiKey).toBe('options-api-key');
    });

    it('should use default base URL', () => {
      const config = new Config({ apiKey: 'test-key' });
      expect(config.baseUrl).toBe('https://api.ambertrace.io');
    });

    it('should accept custom base URL from options', () => {
      const config = new Config({ apiKey: 'test-key', baseUrl: 'https://custom.api.com' });
      expect(config.baseUrl).toBe('https://custom.api.com');
    });

    it('should accept base URL from environment variable', () => {
      process.env.AMBERTRACE_API_KEY = 'test-key';
      process.env.AMBERTRACE_BASE_URL = 'https://env.api.com';
      const config = new Config();
      expect(config.baseUrl).toBe('https://env.api.com');
    });

    it('should accept environment from options', () => {
      const config = new Config({ apiKey: 'test-key', environment: 'production' });
      expect(config.environment).toBe('production');
    });

    it('should accept environment from environment variable', () => {
      process.env.AMBERTRACE_API_KEY = 'test-key';
      process.env.AMBERTRACE_ENVIRONMENT = 'staging';
      const config = new Config();
      expect(config.environment).toBe('staging');
    });

    it('should default debug to false', () => {
      const config = new Config({ apiKey: 'test-key' });
      expect(config.debug).toBe(false);
    });

    it('should accept debug from options', () => {
      const config = new Config({ apiKey: 'test-key', debug: true });
      expect(config.debug).toBe(true);
    });

    it('should accept debug from environment variable', () => {
      process.env.AMBERTRACE_API_KEY = 'test-key';
      process.env.AMBERTRACE_DEBUG = 'true';
      const config = new Config();
      expect(config.debug).toBe(true);
    });

    it('should default timeout to 5000ms', () => {
      const config = new Config({ apiKey: 'test-key' });
      expect(config.timeout).toBe(5000);
    });

    it('should accept custom timeout from options', () => {
      const config = new Config({ apiKey: 'test-key', timeout: 10000 });
      expect(config.timeout).toBe(10000);
    });

    it('should accept timeout from environment variable', () => {
      process.env.AMBERTRACE_API_KEY = 'test-key';
      process.env.AMBERTRACE_TIMEOUT = '15000';
      const config = new Config();
      expect(config.timeout).toBe(15000);
    });

    it('should default enabled to true', () => {
      const config = new Config({ apiKey: 'test-key' });
      expect(config.enabled).toBe(true);
    });

    it('should accept enabled from options', () => {
      const config = new Config({ apiKey: 'test-key', enabled: false });
      expect(config.enabled).toBe(false);
    });

    it('should accept enabled from environment variable', () => {
      process.env.AMBERTRACE_API_KEY = 'test-key';
      process.env.AMBERTRACE_ENABLED = 'false';
      const config = new Config();
      expect(config.enabled).toBe(false);
    });
  });

  describe('getTraceEndpoint', () => {
    it('should return correct trace endpoint URL', () => {
      const config = new Config({ apiKey: 'test-key', baseUrl: 'https://api.example.com' });
      expect(config.getTraceEndpoint()).toBe('https://api.example.com/api/traces/ingest');
    });
  });

  describe('getAuthHeader', () => {
    it('should return Bearer token format', () => {
      const config = new Config({ apiKey: 'my-api-key' });
      expect(config.getAuthHeader()).toBe('Bearer my-api-key');
    });
  });
});

describe('Global config functions', () => {
  beforeEach(() => {
    clearConfig();
  });

  describe('setConfig and getConfig', () => {
    it('should store and retrieve config', () => {
      const config = new Config({ apiKey: 'test-key' });
      setConfig(config);
      expect(getConfig()).toBe(config);
    });

    it('should return null when no config set', () => {
      expect(getConfig()).toBeNull();
    });
  });

  describe('clearConfig', () => {
    it('should clear the stored config', () => {
      const config = new Config({ apiKey: 'test-key' });
      setConfig(config);
      clearConfig();
      expect(getConfig()).toBeNull();
    });
  });
});

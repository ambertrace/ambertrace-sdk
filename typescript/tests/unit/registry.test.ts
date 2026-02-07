/**
 * Tests for ProviderRegistry.
 */
import { ProviderRegistry } from '../../src/providers/registry';
import type { BaseInterceptor, BaseCollector } from '../../src/providers/base';

// Create mock interceptor
const createMockInterceptor = (): jest.Mocked<BaseInterceptor> => ({
  getProviderName: jest.fn().mockReturnValue('mock'),
  patch: jest.fn(),
  unpatch: jest.fn(),
  isPatched: jest.fn().mockReturnValue(false),
});

// Create mock collector
const createMockCollector = (): jest.Mocked<BaseCollector> => ({
  getProviderName: jest.fn().mockReturnValue('mock'),
  collectTrace: jest.fn().mockReturnValue(null),
});

describe('ProviderRegistry', () => {
  let registry: ProviderRegistry;

  beforeEach(() => {
    registry = new ProviderRegistry();
  });

  describe('registerProvider', () => {
    it('should register a provider', () => {
      const interceptor = createMockInterceptor();
      const collector = createMockCollector();

      registry.registerProvider('openai', interceptor, collector);

      expect(registry.hasProvider('openai')).toBe(true);
    });

    it('should allow registering multiple providers', () => {
      const openaiInterceptor = createMockInterceptor();
      const openaiCollector = createMockCollector();
      const anthropicInterceptor = createMockInterceptor();
      const anthropicCollector = createMockCollector();

      registry.registerProvider('openai', openaiInterceptor, openaiCollector);
      registry.registerProvider('anthropic', anthropicInterceptor, anthropicCollector);

      expect(registry.hasProvider('openai')).toBe(true);
      expect(registry.hasProvider('anthropic')).toBe(true);
    });

    it('should overwrite existing provider', () => {
      const interceptor1 = createMockInterceptor();
      const collector1 = createMockCollector();
      const interceptor2 = createMockInterceptor();
      const collector2 = createMockCollector();

      registry.registerProvider('openai', interceptor1, collector1);
      registry.registerProvider('openai', interceptor2, collector2);

      expect(registry.getInterceptor('openai')).toBe(interceptor2);
    });
  });

  describe('unregisterProvider', () => {
    it('should unregister a provider', () => {
      const interceptor = createMockInterceptor();
      const collector = createMockCollector();

      registry.registerProvider('openai', interceptor, collector);
      registry.unregisterProvider('openai');

      expect(registry.hasProvider('openai')).toBe(false);
    });

    it('should unpatch interceptor when unregistering', () => {
      const interceptor = createMockInterceptor();
      interceptor.isPatched.mockReturnValue(true);
      const collector = createMockCollector();

      registry.registerProvider('openai', interceptor, collector);
      registry.unregisterProvider('openai');

      expect(interceptor.unpatch).toHaveBeenCalled();
    });

    it('should not fail when unregistering non-existent provider', () => {
      expect(() => registry.unregisterProvider('nonexistent')).not.toThrow();
    });
  });

  describe('patchAll', () => {
    it('should patch all registered providers', () => {
      const openaiInterceptor = createMockInterceptor();
      const anthropicInterceptor = createMockInterceptor();

      registry.registerProvider('openai', openaiInterceptor, createMockCollector());
      registry.registerProvider('anthropic', anthropicInterceptor, createMockCollector());

      registry.patchAll();

      expect(openaiInterceptor.patch).toHaveBeenCalled();
      expect(anthropicInterceptor.patch).toHaveBeenCalled();
    });

    it('should continue patching other providers if one fails', () => {
      const failingInterceptor = createMockInterceptor();
      failingInterceptor.patch.mockImplementation(() => {
        throw new Error('Patch failed');
      });
      const successInterceptor = createMockInterceptor();

      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

      registry.registerProvider('failing', failingInterceptor, createMockCollector());
      registry.registerProvider('success', successInterceptor, createMockCollector());

      registry.patchAll();

      expect(successInterceptor.patch).toHaveBeenCalled();

      consoleErrorSpy.mockRestore();
    });
  });

  describe('unpatchAll', () => {
    it('should unpatch all registered providers', () => {
      const openaiInterceptor = createMockInterceptor();
      const anthropicInterceptor = createMockInterceptor();

      registry.registerProvider('openai', openaiInterceptor, createMockCollector());
      registry.registerProvider('anthropic', anthropicInterceptor, createMockCollector());

      registry.unpatchAll();

      expect(openaiInterceptor.unpatch).toHaveBeenCalled();
      expect(anthropicInterceptor.unpatch).toHaveBeenCalled();
    });

    it('should continue unpatching other providers if one fails', () => {
      const failingInterceptor = createMockInterceptor();
      failingInterceptor.unpatch.mockImplementation(() => {
        throw new Error('Unpatch failed');
      });
      const successInterceptor = createMockInterceptor();

      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

      registry.registerProvider('failing', failingInterceptor, createMockCollector());
      registry.registerProvider('success', successInterceptor, createMockCollector());

      registry.unpatchAll();

      expect(successInterceptor.unpatch).toHaveBeenCalled();

      consoleErrorSpy.mockRestore();
    });
  });

  describe('getCollector', () => {
    it('should return collector for registered provider', () => {
      const collector = createMockCollector();
      registry.registerProvider('openai', createMockInterceptor(), collector);

      expect(registry.getCollector('openai')).toBe(collector);
    });

    it('should return undefined for non-existent provider', () => {
      expect(registry.getCollector('nonexistent')).toBeUndefined();
    });
  });

  describe('getInterceptor', () => {
    it('should return interceptor for registered provider', () => {
      const interceptor = createMockInterceptor();
      registry.registerProvider('openai', interceptor, createMockCollector());

      expect(registry.getInterceptor('openai')).toBe(interceptor);
    });

    it('should return undefined for non-existent provider', () => {
      expect(registry.getInterceptor('nonexistent')).toBeUndefined();
    });
  });

  describe('getProviderNames', () => {
    it('should return empty array when no providers registered', () => {
      expect(registry.getProviderNames()).toEqual([]);
    });

    it('should return all registered provider names', () => {
      registry.registerProvider('openai', createMockInterceptor(), createMockCollector());
      registry.registerProvider('anthropic', createMockInterceptor(), createMockCollector());

      const names = registry.getProviderNames();
      expect(names).toContain('openai');
      expect(names).toContain('anthropic');
      expect(names).toHaveLength(2);
    });
  });

  describe('hasProvider', () => {
    it('should return false for non-existent provider', () => {
      expect(registry.hasProvider('openai')).toBe(false);
    });

    it('should return true for registered provider', () => {
      registry.registerProvider('openai', createMockInterceptor(), createMockCollector());

      expect(registry.hasProvider('openai')).toBe(true);
    });
  });

  describe('clear', () => {
    it('should remove all providers', () => {
      registry.registerProvider('openai', createMockInterceptor(), createMockCollector());
      registry.registerProvider('anthropic', createMockInterceptor(), createMockCollector());

      registry.clear();

      expect(registry.getProviderNames()).toHaveLength(0);
      expect(registry.hasProvider('openai')).toBe(false);
      expect(registry.hasProvider('anthropic')).toBe(false);
    });

    it('should unpatch all providers before clearing', () => {
      const interceptor = createMockInterceptor();
      registry.registerProvider('openai', interceptor, createMockCollector());

      registry.clear();

      expect(interceptor.unpatch).toHaveBeenCalled();
    });
  });
});

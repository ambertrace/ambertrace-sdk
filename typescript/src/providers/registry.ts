/**
 * Provider registry for managing multiple LLM provider interceptors and collectors.
 *
 * The registry:
 * - Maintains a mapping of provider name → (interceptor, collector)
 * - Allows patching/unpatching all providers at once
 * - Isolates failures (one provider error doesn't affect others)
 * - Provides lookup methods for collectors during trace collection
 */

import type { BaseInterceptor, BaseCollector } from './base';

/**
 * Manages registration and lifecycle of all LLM provider integrations.
 */
export class ProviderRegistry {
  private interceptors: Map<string, BaseInterceptor> = new Map();
  private collectors: Map<string, BaseCollector> = new Map();

  /**
   * Register a new provider with its interceptor and collector.
   *
   * @param name - Provider name (e.g., "openai", "anthropic")
   * @param interceptor - Interceptor instance for this provider
   * @param collector - Collector instance for this provider
   */
  registerProvider(
    name: string,
    interceptor: BaseInterceptor,
    collector: BaseCollector
  ): void {
    this.interceptors.set(name, interceptor);
    this.collectors.set(name, collector);
  }

  /**
   * Apply interception to all registered providers.
   *
   * Errors in individual providers are logged but don't prevent
   * other providers from being patched.
   */
  patchAll(): void {
    for (const [name, interceptor] of this.interceptors) {
      try {
        interceptor.patch();
      } catch (error) {
        console.error(`[AmberTrace] Failed to patch ${name}:`, error);
      }
    }
  }

  /**
   * Remove interception from all registered providers.
   */
  unpatchAll(): void {
    for (const [name, interceptor] of this.interceptors) {
      try {
        interceptor.unpatch();
      } catch (error) {
        console.error(`[AmberTrace] Failed to unpatch ${name}:`, error);
      }
    }
  }

  /**
   * Get collector for a specific provider.
   *
   * @param name - Provider name
   * @returns Collector instance, or undefined if not registered
   */
  getCollector(name: string): BaseCollector | undefined {
    return this.collectors.get(name);
  }

  /**
   * Get interceptor for a specific provider.
   *
   * @param name - Provider name
   * @returns Interceptor instance, or undefined if not registered
   */
  getInterceptor(name: string): BaseInterceptor | undefined {
    return this.interceptors.get(name);
  }

  /**
   * Get all registered provider names.
   */
  getProviderNames(): string[] {
    return Array.from(this.interceptors.keys());
  }

  /**
   * Check if a provider is registered.
   *
   * @param name - Provider name
   */
  hasProvider(name: string): boolean {
    return this.interceptors.has(name);
  }

  /**
   * Unregister a provider.
   *
   * @param name - Provider name
   */
  unregisterProvider(name: string): void {
    const interceptor = this.interceptors.get(name);
    if (interceptor?.isPatched()) {
      try {
        interceptor.unpatch();
      } catch (error) {
        console.error(`[AmberTrace] Failed to unpatch ${name} during unregister:`, error);
      }
    }
    this.interceptors.delete(name);
    this.collectors.delete(name);
  }

  /**
   * Clear all registered providers.
   */
  clear(): void {
    this.unpatchAll();
    this.interceptors.clear();
    this.collectors.clear();
  }
}

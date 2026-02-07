/**
 * Base interfaces for provider abstraction.
 *
 * All LLM provider implementations (OpenAI, Anthropic, etc.) must implement
 * these interfaces to ensure consistent behavior and unified trace format.
 */

import type { Trace } from '../models';

/**
 * Base interface for LLM provider interceptors.
 *
 * Interceptors are responsible for:
 * - Monkey-patching/proxying the provider's SDK methods
 * - Capturing request/response data
 * - Triggering trace collection
 * - Preserving original SDK behavior exactly
 */
export interface BaseInterceptor {
  /**
   * Apply interception to the provider's SDK.
   * Should be idempotent (safe to call multiple times).
   */
  patch(): void;

  /**
   * Remove interception and restore original SDK behavior.
   * Should be idempotent (safe to call multiple times).
   */
  unpatch(): void;

  /**
   * Check if interception is currently active.
   */
  isPatched(): boolean;

  /**
   * Get the provider name (e.g., "openai", "anthropic").
   */
  getProviderName(): string;
}

/**
 * Base interface for trace collectors.
 *
 * Collectors are responsible for:
 * - Extracting data from provider-specific request/response objects
 * - Normalizing data to unified trace format
 * - Enriching traces with metadata (timestamp, SDK version, etc.)
 * - Serializing traces to JSON
 * - Never raising exceptions (defensive error handling)
 */
export interface BaseCollector {
  /**
   * Collect and serialize a trace from a provider API call.
   *
   * @param traceId - Unique trace identifier (UUID)
   * @param startTime - Start timestamp in milliseconds
   * @param requestArgs - Arguments passed to provider API call
   * @param response - Provider response object (if successful)
   * @param error - Error object (if call failed)
   * @returns Serialized trace object, or null if collection fails
   */
  collectTrace(
    traceId: string,
    startTime: number,
    requestArgs: Record<string, unknown>,
    response?: unknown,
    error?: Error
  ): Trace | null;

  /**
   * Get the provider name (e.g., "openai", "anthropic").
   */
  getProviderName(): string;
}

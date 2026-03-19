/**
 * AmberTrace TypeScript/Node.js SDK - Main Entry Point
 *
 * Public API for tracing LLM calls (OpenAI, Anthropic, Google Gemini) to AmberTrace platform.
 *
 * Usage:
 *   import ambertrace from '@ambertrace/node';
 *
 *   ambertrace.init({ apiKey: 'your-api-key' });
 *
 *   // Use OpenAI/Anthropic/Gemini as normal - calls are automatically traced
 */

import { Config, setConfig, getConfig, clearConfig, type ConfigOptions } from './config';
import { getTransport, clearTransport } from './transport';
import { ProviderRegistry } from './providers/registry';
import { OpenAIInterceptor } from './providers/openai/interceptor';
import { OpenAICollector } from './providers/openai/collector';
import { AnthropicInterceptor } from './providers/anthropic/interceptor';
import { AnthropicCollector } from './providers/anthropic/collector';
import { GeminiInterceptor } from './providers/gemini/interceptor';
import { GeminiCollector } from './providers/gemini/collector';
import { VERSION } from './version';

// Global provider registry
let globalRegistry: ProviderRegistry | null = null;

/**
 * Initialize AmberTrace SDK and start tracing LLM calls.
 *
 * This function:
 * - Validates and stores configuration
 * - Auto-detects installed LLM SDKs (OpenAI, Anthropic, Google Gemini)
 * - Applies interception to detected providers
 * - Starts async trace delivery
 *
 * @param options - Configuration options
 *
 * @example
 * ```typescript
 * import ambertrace from '@ambertrace/node';
 *
 * ambertrace.init({
 *   apiKey: 'your-api-key',
 *   environment: 'production',
 *   debug: false,
 * });
 * ```
 */
export function init(options: ConfigOptions = {}): void {
  try {
    // Create and store configuration
    const config = new Config(options);
    setConfig(config);

    // Create provider registry
    const registry = new ProviderRegistry();

    // Auto-detect and register OpenAI
    try {
      require.resolve('openai');
      registry.registerProvider('openai', new OpenAIInterceptor(), new OpenAICollector());
      if (config.debug) {
        console.log('[AmberTrace] OpenAI SDK detected and registered');
      }
    } catch {
      if (config.debug) {
        console.log('[AmberTrace] OpenAI SDK not found, skipping');
      }
    }

    // Auto-detect and register Anthropic
    try {
      require.resolve('@anthropic-ai/sdk');
      registry.registerProvider(
        'anthropic',
        new AnthropicInterceptor(),
        new AnthropicCollector()
      );
      if (config.debug) {
        console.log('[AmberTrace] Anthropic SDK detected and registered');
      }
    } catch {
      if (config.debug) {
        console.log('[AmberTrace] Anthropic SDK not found, skipping');
      }
    }

    // Auto-detect and register Google Gemini (either SDK)
    {
      let geminiAvailable = false;
      try {
        require.resolve('@google/generative-ai');
        geminiAvailable = true;
      } catch {
        // Original Gemini SDK not available
      }
      try {
        require.resolve('@google/genai');
        geminiAvailable = true;
      } catch {
        // Newer Gemini SDK not available
      }
      if (geminiAvailable) {
        registry.registerProvider(
          'gemini',
          new GeminiInterceptor(),
          new GeminiCollector()
        );
        if (config.debug) {
          console.log('[AmberTrace] Gemini SDK detected and registered');
        }
      } else if (config.debug) {
        console.log('[AmberTrace] Gemini SDK not found, skipping');
      }
    }

    // Store registry globally
    globalRegistry = registry;

    // Apply patches if tracing is enabled
    if (config.enabled) {
      registry.patchAll();
    }

    if (config.debug) {
      const providers = registry.getProviderNames();
      console.log(`[AmberTrace] Initialized with providers: ${providers.join(', ')}`);
      console.log(`[AmberTrace] Tracing enabled: ${config.enabled}`);
    }
  } catch (error) {
    console.error('[AmberTrace] Failed to initialize:', error);
    throw error;
  }
}

/**
 * Enable tracing (apply interception to all registered providers).
 *
 * @example
 * ```typescript
 * ambertrace.enable();
 * ```
 */
export function enable(): void {
  const config = getConfig();
  if (config && globalRegistry) {
    globalRegistry.patchAll();
    if (config.debug) {
      console.log('[AmberTrace] Tracing enabled');
    }
  }
}

/**
 * Disable tracing (remove interception from all providers).
 *
 * @example
 * ```typescript
 * ambertrace.disable();
 * ```
 */
export function disable(): void {
  const config = getConfig();
  if (globalRegistry) {
    globalRegistry.unpatchAll();
    if (config?.debug) {
      console.log('[AmberTrace] Tracing disabled');
    }
  }
}

/**
 * Check if tracing is currently enabled.
 *
 * @returns True if at least one provider is patched
 *
 * @example
 * ```typescript
 * if (ambertrace.isEnabled()) {
 *   console.log('Tracing is active');
 * }
 * ```
 */
export function isEnabled(): boolean {
  if (!globalRegistry) {
    return false;
  }

  // Check if any provider is patched
  const providers = globalRegistry.getProviderNames();
  for (const name of providers) {
    const interceptor = globalRegistry.getInterceptor(name);
    if (interceptor?.isPatched()) {
      return true;
    }
  }

  return false;
}

/**
 * Wait for all pending traces to be sent to the backend.
 *
 * Call this before process exit to ensure all traces are delivered.
 *
 * @param timeoutMs - Maximum time to wait in milliseconds (default: 5000)
 *
 * @example
 * ```typescript
 * // Before exiting
 * await ambertrace.flush(10000);
 * process.exit(0);
 * ```
 */
export async function flush(timeoutMs: number = 5000): Promise<void> {
  const transport = getTransport();
  await transport.flush(timeoutMs);
}

/**
 * Shutdown the SDK and clean up resources.
 *
 * This function:
 * - Removes all interception
 * - Flushes pending traces
 * - Clears configuration and transport
 *
 * @param timeoutMs - Maximum time to wait for flush (default: 5000)
 *
 * @example
 * ```typescript
 * await ambertrace.shutdown();
 * ```
 */
export async function shutdown(timeoutMs: number = 5000): Promise<void> {
  const config = getConfig();

  // Unpatch all providers
  if (globalRegistry) {
    globalRegistry.unpatchAll();
    globalRegistry.clear();
    globalRegistry = null;
  }

  // Flush pending traces
  await flush(timeoutMs);

  // Clear global state
  clearConfig();
  clearTransport();

  if (config?.debug) {
    console.log('[AmberTrace] SDK shutdown complete');
  }
}

/**
 * Start a new trace session by rotating the trace_session_id.
 *
 * Useful for long-running apps that want to group traces into logical runs.
 *
 * @returns The new trace_session_id, or undefined if not initialized.
 */
export function newSession(): string | undefined {
  const config = getConfig();
  if (!config) {
    console.warn('[AmberTrace] SDK not initialized, call init() first');
    return undefined;
  }
  return config.newSession();
}

/**
 * Get SDK version.
 */
export function getVersion(): string {
  return VERSION;
}

// Default export
export default {
  init,
  enable,
  disable,
  isEnabled,
  flush,
  shutdown,
  newSession,
  getVersion,
  VERSION,
};

// Named exports for convenience
export { VERSION };
export type { ConfigOptions } from './config';
export type { Trace, RequestData, ResponseData, ErrorData } from './models';

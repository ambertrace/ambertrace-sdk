/**
 * Configuration management for AmberTrace SDK.
 *
 * Handles:
 * - Loading configuration from parameters or environment variables
 * - Validation of required fields
 * - Providing default values
 * - Thread-safe global configuration access
 */

/**
 * Configuration options for AmberTrace SDK initialization.
 */
export interface ConfigOptions {
  /**
   * AmberTrace API key for authentication.
   * Can also be set via AMBERTRACE_API_KEY environment variable.
   */
  apiKey?: string;

  /**
   * Base URL for AmberTrace backend API.
   * Default: https://api.ambertrace.io
   */
  baseUrl?: string;

  /**
   * Environment name to tag traces (e.g., "production", "staging", "development").
   * Helps filter traces in the AmberTrace dashboard.
   */
  environment?: string;

  /**
   * Enable debug logging to console.
   * Default: false
   */
  debug?: boolean;

  /**
   * HTTP request timeout in milliseconds.
   * Default: 5000 (5 seconds)
   */
  timeout?: number;

  /**
   * Whether tracing is enabled.
   * Default: true
   */
  enabled?: boolean;
}

/**
 * Validated and normalized configuration.
 */
export class Config {
  readonly apiKey: string;
  readonly baseUrl: string;
  readonly environment: string | undefined;
  readonly debug: boolean;
  readonly timeout: number;
  readonly enabled: boolean;

  constructor(options: ConfigOptions = {}) {
    // Load API key from parameter or environment variable
    this.apiKey = options.apiKey ?? process.env.AMBERTRACE_API_KEY ?? '';
    if (!this.apiKey) {
      throw new Error(
        'AmberTrace API key is required. ' +
          'Provide it via apiKey parameter or AMBERTRACE_API_KEY environment variable.'
      );
    }

    // Load base URL with default
    this.baseUrl =
      options.baseUrl ?? process.env.AMBERTRACE_BASE_URL ?? 'https://api.ambertrace.io';

    // Load environment (optional)
    this.environment = options.environment ?? process.env.AMBERTRACE_ENVIRONMENT;

    // Load debug flag with default
    const debugEnv = process.env.AMBERTRACE_DEBUG;
    this.debug = options.debug ?? (debugEnv ? debugEnv.toLowerCase() === 'true' : false);

    // Load timeout with default (5 seconds)
    const timeoutEnv = process.env.AMBERTRACE_TIMEOUT;
    this.timeout = options.timeout ?? (timeoutEnv ? parseInt(timeoutEnv, 10) : 5000);

    // Load enabled flag with default
    const enabledEnv = process.env.AMBERTRACE_ENABLED;
    this.enabled = options.enabled ?? (enabledEnv ? enabledEnv.toLowerCase() === 'true' : true);
  }

  /**
   * Get trace endpoint URL.
   */
  getTraceEndpoint(): string {
    return `${this.baseUrl}/api/traces/ingest`;
  }

  /**
   * Get authorization header value.
   */
  getAuthHeader(): string {
    return `Bearer ${this.apiKey}`;
  }
}

// Global configuration instance
let globalConfig: Config | null = null;

/**
 * Set the global configuration.
 *
 * @param config - Configuration instance
 */
export function setConfig(config: Config): void {
  globalConfig = config;
}

/**
 * Get the global configuration.
 *
 * @returns Current configuration, or null if not initialized
 */
export function getConfig(): Config | null {
  return globalConfig;
}

/**
 * Clear the global configuration.
 */
export function clearConfig(): void {
  globalConfig = null;
}

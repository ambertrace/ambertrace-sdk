/**
 * OpenAI SDK interceptor using prototype manipulation.
 *
 * Intercepts chat.completions.create() to collect traces transparently.
 */

import { randomUUID } from 'crypto';
import type { BaseInterceptor } from '../base';
import { OpenAICollector } from './collector';
import { getTransport } from '../../transport';
import { getConfig } from '../../config';

/**
 * Intercepts OpenAI SDK chat completion calls.
 */
export class OpenAIInterceptor implements BaseInterceptor {
  private collector = new OpenAICollector();
  private isCurrentlyPatched = false;
  private originalCreate: ((...args: unknown[]) => unknown) | null = null;

  getProviderName(): string {
    return 'openai';
  }

  patch(): void {
    if (this.isCurrentlyPatched) {
      return; // Already patched
    }

    try {
      // Try to import OpenAI SDK
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const openai = require('openai');

      // Access the Completions class prototype
      const CompletionsClass = openai.OpenAI?.Chat?.Completions;
      if (!CompletionsClass || !CompletionsClass.prototype) {
        throw new Error('OpenAI SDK structure not recognized');
      }

      const prototype = CompletionsClass.prototype;

      // Store original create method
      this.originalCreate = prototype.create;

      if (typeof this.originalCreate !== 'function') {
        throw new Error('chat.completions.create is not a function');
      }

      // Create wrapper
      const originalMethod = this.originalCreate;
      const self = this;

      prototype.create = function wrappedCreate(...args: unknown[]) {
        const config = getConfig();

        // If tracing is disabled, call original method
        if (!config?.enabled) {
          return originalMethod.apply(this, args);
        }

        // Extract request arguments
        // OpenAI SDK: create(body, options)
        const requestArgs = (args[0] as Record<string, unknown>) ?? {};

        // Generate trace ID and start time
        const traceId = randomUUID();
        const startTime = Date.now();

        try {
          // Call original method
          const result = originalMethod.apply(this, args);

          // Check if result is a promise (async)
          if (result && typeof (result as Promise<unknown>).then === 'function') {
            return (result as Promise<unknown>)
              .then((response) => {
                // Collect trace on success
                self.collectAndSendTrace(traceId, startTime, requestArgs, response);
                return response;
              })
              .catch((error: Error) => {
                // Collect trace on error, then re-throw
                self.collectAndSendTrace(traceId, startTime, requestArgs, undefined, error);
                throw error;
              });
          }

          // Synchronous result (unlikely for OpenAI SDK)
          self.collectAndSendTrace(traceId, startTime, requestArgs, result);
          return result;
        } catch (error) {
          // Collect trace on exception, then re-throw
          self.collectAndSendTrace(
            traceId,
            startTime,
            requestArgs,
            undefined,
            error as Error
          );
          throw error;
        }
      };

      this.isCurrentlyPatched = true;

      if (getConfig()?.debug) {
        console.log('[AmberTrace] OpenAI SDK patched successfully');
      }
    } catch (error) {
      console.error('[AmberTrace] Failed to patch OpenAI SDK:', error);
      throw error;
    }
  }

  unpatch(): void {
    if (!this.isCurrentlyPatched || !this.originalCreate) {
      return;
    }

    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const openai = require('openai');
      const CompletionsClass = openai.OpenAI?.Chat?.Completions;

      if (CompletionsClass?.prototype) {
        CompletionsClass.prototype.create = this.originalCreate;
      }

      this.isCurrentlyPatched = false;
      this.originalCreate = null;

      if (getConfig()?.debug) {
        console.log('[AmberTrace] OpenAI SDK unpatched');
      }
    } catch (error) {
      console.error('[AmberTrace] Failed to unpatch OpenAI SDK:', error);
    }
  }

  isPatched(): boolean {
    return this.isCurrentlyPatched;
  }

  private collectAndSendTrace(
    traceId: string,
    startTime: number,
    requestArgs: Record<string, unknown>,
    response?: unknown,
    error?: Error
  ): void {
    try {
      // Collect trace
      const trace = this.collector.collectTrace(traceId, startTime, requestArgs, response, error);

      if (trace) {
        // Send trace asynchronously
        const transport = getTransport();
        transport.sendTrace(trace);
      }
    } catch (err) {
      // Never throw from trace collection
      if (getConfig()?.debug) {
        console.error('[AmberTrace] Error collecting/sending trace:', err);
      }
    }
  }
}

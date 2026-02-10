/**
 * Google Gemini SDK interceptor using prototype manipulation.
 *
 * Supports both Gemini SDKs:
 * - @google/generative-ai (original SDK): patches GenerativeModel.prototype.generateContent
 * - @google/genai (newer SDK): patches models resource class generateContent
 *
 * Intercepts generateContent() calls to collect traces transparently.
 */

import { randomUUID } from 'crypto';
import type { BaseInterceptor } from '../base';
import { GeminiCollector } from './collector';
import { getTransport } from '../../transport';
import { getConfig } from '../../config';

/**
 * Intercepts Google Gemini SDK content generation calls.
 *
 * Supports patching both the original @google/generative-ai SDK and
 * the newer @google/genai SDK independently.
 */
export class GeminiInterceptor implements BaseInterceptor {
  private collector = new GeminiCollector();

  // Original SDK state
  private genaiPatched = false;
  private originalGenaiGenerateContent: ((...args: unknown[]) => unknown) | null = null;
  private genaiPrototype: Record<string, unknown> | null = null;

  // Newer SDK state
  private genai2Patched = false;
  private originalGenai2GenerateContent: ((...args: unknown[]) => unknown) | null = null;
  private genai2Prototype: Record<string, unknown> | null = null;

  getProviderName(): string {
    return 'google';
  }

  patch(): void {
    // Patch original SDK
    if (!this.genaiPatched) {
      try {
        this.patchOriginalSdk();
      } catch {
        // Original SDK not available, skip
      }
    }

    // Patch newer SDK
    if (!this.genai2Patched) {
      try {
        this.patchNewerSdk();
      } catch {
        // Newer SDK not available, skip
      }
    }

    if (getConfig()?.debug) {
      const parts: string[] = [];
      if (this.genaiPatched) parts.push('@google/generative-ai');
      if (this.genai2Patched) parts.push('@google/genai');
      if (parts.length > 0) {
        console.log(`[AmberTrace] Gemini SDK patched: ${parts.join(', ')}`);
      }
    }
  }

  unpatch(): void {
    // Unpatch original SDK
    if (this.genaiPatched && this.genaiPrototype && this.originalGenaiGenerateContent) {
      this.genaiPrototype.generateContent = this.originalGenaiGenerateContent;
      this.genaiPatched = false;
      this.originalGenaiGenerateContent = null;
      this.genaiPrototype = null;
    }

    // Unpatch newer SDK
    if (this.genai2Patched && this.genai2Prototype && this.originalGenai2GenerateContent) {
      this.genai2Prototype.generateContent = this.originalGenai2GenerateContent;
      this.genai2Patched = false;
      this.originalGenai2GenerateContent = null;
      this.genai2Prototype = null;
    }

    if (getConfig()?.debug) {
      console.log('[AmberTrace] Gemini SDK unpatched');
    }
  }

  isPatched(): boolean {
    return this.genaiPatched || this.genai2Patched;
  }

  private patchOriginalSdk(): void {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const genai = require('@google/generative-ai');

    // Try to find GenerativeModel class
    const ModelClass = genai.GenerativeModel;
    if (!ModelClass?.prototype) {
      throw new Error('GenerativeModel not found in @google/generative-ai');
    }

    const prototype = ModelClass.prototype;

    if (typeof prototype.generateContent !== 'function') {
      throw new Error('generateContent is not a function');
    }

    // Store original
    this.originalGenaiGenerateContent = prototype.generateContent;
    this.genaiPrototype = prototype;

    // Create wrapper - capture reference as non-null (we verified above)
    const originalMethod = this.originalGenaiGenerateContent!;
    const self = this;

    prototype.generateContent = function wrappedGenerateContent(
      this: Record<string, unknown>,
      ...args: unknown[]
    ) {
      const config = getConfig();

      // If tracing is disabled, call original method
      if (!config?.enabled) {
        return originalMethod.apply(this, args);
      }

      // Extract model name from instance
      const modelName = this.model ?? 'unknown';

      // Build request kwargs
      const requestArgs: Record<string, unknown> = {
        _ambertrace_model: modelName,
      };

      // Extract contents from positional args
      if (args.length > 0) {
        requestArgs.contents = args[0];
      }

      // Merge any remaining kwargs
      if (args.length > 1 && typeof args[1] === 'object' && args[1] !== null) {
        Object.assign(requestArgs, args[1] as Record<string, unknown>);
      }

      // Generate trace ID and start time
      const traceId = randomUUID();
      const startTime = Date.now();

      try {
        const result = originalMethod.apply(this, args);

        // Check if result is a promise
        if (result && typeof (result as Promise<unknown>).then === 'function') {
          return (result as Promise<unknown>)
            .then((response) => {
              self.collectAndSendTrace(traceId, startTime, requestArgs, response);
              return response;
            })
            .catch((error: Error) => {
              self.collectAndSendTrace(traceId, startTime, requestArgs, undefined, error);
              throw error;
            });
        }

        // Synchronous result
        self.collectAndSendTrace(traceId, startTime, requestArgs, result);
        return result;
      } catch (error) {
        self.collectAndSendTrace(traceId, startTime, requestArgs, undefined, error as Error);
        throw error;
      }
    };

    this.genaiPatched = true;
  }

  private patchNewerSdk(): void {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const genai = require('@google/genai');

    // Newer SDK exposes models resource, find the prototype to patch
    const GoogleGenAI = genai.GoogleGenAI;
    if (!GoogleGenAI) {
      throw new Error('GoogleGenAI not found in @google/genai');
    }

    // The newer SDK has a Models class that has generateContent
    // We need to find it - it could be on the GoogleGenAI instance's models property
    const ModelsClass = genai.Models ?? genai.GoogleGenAI?.Models;
    if (!ModelsClass?.prototype) {
      throw new Error('Models class not found in @google/genai');
    }

    const prototype = ModelsClass.prototype;

    if (typeof prototype.generateContent !== 'function') {
      throw new Error('generateContent is not a function on Models');
    }

    // Store original
    this.originalGenai2GenerateContent = prototype.generateContent;
    this.genai2Prototype = prototype;

    // Create wrapper - capture reference as non-null (we verified above)
    const originalMethod = this.originalGenai2GenerateContent!;
    const self = this;

    prototype.generateContent = function wrappedGenerateContent(
      this: Record<string, unknown>,
      ...args: unknown[]
    ) {
      const config = getConfig();

      // If tracing is disabled, call original method
      if (!config?.enabled) {
        return originalMethod.apply(this, args);
      }

      // Newer SDK: generateContent({ model, contents, ... })
      const requestArgs: Record<string, unknown> = {};
      if (args.length > 0 && typeof args[0] === 'object' && args[0] !== null) {
        Object.assign(requestArgs, args[0] as Record<string, unknown>);
      }

      // Generate trace ID and start time
      const traceId = randomUUID();
      const startTime = Date.now();

      try {
        const result = originalMethod.apply(this, args);

        // Check if result is a promise
        if (result && typeof (result as Promise<unknown>).then === 'function') {
          return (result as Promise<unknown>)
            .then((response) => {
              self.collectAndSendTrace(traceId, startTime, requestArgs, response);
              return response;
            })
            .catch((error: Error) => {
              self.collectAndSendTrace(traceId, startTime, requestArgs, undefined, error);
              throw error;
            });
        }

        // Synchronous result
        self.collectAndSendTrace(traceId, startTime, requestArgs, result);
        return result;
      } catch (error) {
        self.collectAndSendTrace(traceId, startTime, requestArgs, undefined, error as Error);
        throw error;
      }
    };

    this.genai2Patched = true;
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
        console.error('[AmberTrace] Error collecting/sending Gemini trace:', err);
      }
    }
  }
}

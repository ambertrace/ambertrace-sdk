/**
 * Trace collection and serialization for Google Gemini.
 *
 * Normalizes Gemini-specific format to match unified trace structure:
 * - contents (string/array) → messages array
 * - prompt_token_count → prompt_tokens
 * - candidates_token_count → completion_tokens
 * - total_token_count → total_tokens
 * - Finish reason: STOP→stop, MAX_TOKENS→length, SAFETY→content_filter
 */

import type { BaseCollector } from '../base';
import type { Trace, RequestData, ResponseData, ErrorData, Message } from '../../models';
import { getConfig } from '../../config';
import { VERSION } from '../../version';

/**
 * Keys that must never appear in trace parameters (security).
 */
const EXCLUDED_PARAM_KEYS = new Set([
  'model',
  'contents',
  '_ambertrace_model',
  'api_key',
  'apiKey',
  'credentials',
  'client',
  '_client',
  'authClient',
  'httpOptions',
]);

/**
 * Gemini finish reason normalization map.
 */
const FINISH_REASON_MAP: Record<string, string> = {
  // String enum values
  STOP: 'stop',
  MAX_TOKENS: 'length',
  SAFETY: 'content_filter',
  RECITATION: 'content_filter',
  OTHER: 'stop',
  FINISH_REASON_UNSPECIFIED: 'stop',
};

/**
 * Integer enum finish reason map.
 */
const FINISH_REASON_INT_MAP: Record<number, string> = {
  0: 'stop', // FINISH_REASON_UNSPECIFIED
  1: 'stop', // STOP
  2: 'length', // MAX_TOKENS
  3: 'content_filter', // SAFETY
  4: 'content_filter', // RECITATION
  5: 'stop', // OTHER
};

/**
 * Collects and builds trace objects from Google Gemini API calls.
 */
export class GeminiCollector implements BaseCollector {
  getProviderName(): string {
    return 'google';
  }

  collectTrace(
    traceId: string,
    startTime: number,
    requestArgs: Record<string, unknown>,
    response?: unknown,
    error?: Error
  ): Trace | null {
    try {
      // Calculate duration
      const endTime = Date.now();
      const durationMs = endTime - startTime;

      // Get current timestamp in ISO 8601 UTC format
      const timestamp = new Date().toISOString();

      // Get configuration
      const config = getConfig();
      const environment = config?.environment;

      // Build request data
      const requestData = this.buildRequestData(requestArgs ?? {});

      // Build response or error data
      let responseData: ResponseData | undefined;
      let errorData: ErrorData | undefined;

      if (response) {
        responseData = this.buildResponseData(response);
      } else if (error) {
        errorData = this.buildErrorData(error);
      }

      // Build trace in unified format
      const trace: Trace = {
        trace_id: traceId,
        timestamp,
        provider: 'google',
        method: 'generate_content',
        duration_ms: durationMs,
        request: requestData,
        response: responseData,
        error: errorData,
        sdk_version: `ambertrace-node/${VERSION}`,
        environment,
      };

      if (config?.debug) {
        console.log(
          `[AmberTrace] Collected Gemini trace ${traceId} (duration: ${durationMs.toFixed(2)}ms)`
        );
      }

      return trace;
    } catch (err) {
      // Never raise exceptions - log and return null
      console.error(`[AmberTrace] Failed to collect Gemini trace ${traceId}:`, err);
      return null;
    }
  }

  private buildRequestData(args: Record<string, unknown>): RequestData {
    // Extract model (may come from _ambertrace_model injected by interceptor,
    // or from 'model' kwarg in newer SDK)
    const model =
      (args._ambertrace_model as string) ?? (args.model as string) ?? 'unknown';

    // Extract and normalize contents to messages
    const contents = args.contents;
    const messages = this.normalizeContents(contents);

    // Extract parameters (exclude sensitive and known keys)
    const parameters: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(args)) {
      if (!EXCLUDED_PARAM_KEYS.has(key)) {
        parameters[key] = value;
      }
    }

    return {
      model,
      messages,
      parameters,
    };
  }

  private normalizeContents(contents: unknown): Message[] {
    const messages: Message[] = [];

    if (contents == null) {
      return messages;
    }

    if (typeof contents === 'string') {
      messages.push({ role: 'user', content: contents });
      return messages;
    }

    if (Array.isArray(contents)) {
      for (const item of contents) {
        if (typeof item === 'string') {
          messages.push({ role: 'user', content: item });
        } else if (typeof item === 'object' && item !== null) {
          // Check for dict-like with role and parts
          if ('role' in item && 'parts' in item) {
            const role = String((item as Record<string, unknown>).role ?? 'user');
            const parts = (item as Record<string, unknown>).parts;
            const text = this.extractTextFromParts(parts);
            messages.push({ role, content: text });
          } else if ('text' in item) {
            // Single Part object
            messages.push({ role: 'user', content: String((item as Record<string, unknown>).text ?? '') });
          }
        }
      }
      return messages;
    }

    // Fallback: try to convert to string
    messages.push({ role: 'user', content: String(contents) });
    return messages;
  }

  private extractTextFromParts(parts: unknown): string {
    if (parts == null) {
      return '';
    }

    if (typeof parts === 'string') {
      return parts;
    }

    if (!Array.isArray(parts)) {
      if (typeof parts === 'object' && parts !== null && 'text' in parts) {
        return String((parts as Record<string, unknown>).text ?? '');
      }
      return String(parts);
    }

    const textParts: string[] = [];
    for (const part of parts) {
      if (typeof part === 'string') {
        textParts.push(part);
      } else if (typeof part === 'object' && part !== null) {
        if ('text' in part) {
          const textVal = (part as Record<string, unknown>).text;
          if (textVal != null) {
            textParts.push(String(textVal));
          }
        }
      }
    }

    return textParts.join(' ');
  }

  private buildResponseData(response: unknown): ResponseData {
    const resp = response as Record<string, unknown>;

    // Extract response ID if available
    const id = String(resp.response_id ?? resp.id ?? 'unknown');

    // Extract model from response if available
    const model = String(resp.model ?? 'unknown');

    // Extract candidates
    const candidates = (resp.candidates as Array<Record<string, unknown>>) ?? [];
    const choices: Array<{ index: number; message: Message; finish_reason: string }> = [];

    for (let i = 0; i < candidates.length; i++) {
      const candidate = candidates[i]!;

      // Extract content text from candidate
      const content = candidate.content as Record<string, unknown> | undefined;
      let text = '';
      if (content) {
        const parts = content.parts;
        text = this.extractTextFromParts(parts);
      }

      // Extract and normalize finish reason
      const rawFinishReason = candidate.finish_reason;
      const finishReason = this.normalizeFinishReason(rawFinishReason);

      choices.push({
        index: i,
        message: {
          role: 'assistant',
          content: text,
        },
        finish_reason: finishReason,
      });
    }

    // If no candidates but response has .text, use that
    if (choices.length === 0) {
      let text = '';
      try {
        const textAttr = resp.text;
        if (typeof textAttr === 'function') {
          text = textAttr();
        } else if (textAttr != null) {
          text = String(textAttr);
        }
      } catch {
        // Ignore
      }

      if (text) {
        choices.push({
          index: 0,
          message: { role: 'assistant', content: text },
          finish_reason: 'stop',
        });
      }
    }

    // Extract usage metadata
    const usageMetadata = resp.usage_metadata ?? resp.usageMetadata;
    let usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number };

    if (usageMetadata && typeof usageMetadata === 'object') {
      const um = usageMetadata as Record<string, unknown>;
      const promptTokens =
        (um.prompt_token_count as number) ?? (um.promptTokenCount as number) ?? 0;
      const completionTokens =
        (um.candidates_token_count as number) ?? (um.candidatesTokenCount as number) ?? 0;
      const totalTokens =
        (um.total_token_count as number) ??
        (um.totalTokenCount as number) ??
        promptTokens + completionTokens;

      usage = {
        prompt_tokens: promptTokens,
        completion_tokens: completionTokens,
        total_tokens: totalTokens,
      };
    } else {
      usage = {
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0,
      };
    }

    return {
      id,
      model,
      choices,
      usage,
    };
  }

  private normalizeFinishReason(rawReason: unknown): string {
    if (rawReason == null) {
      return 'stop';
    }

    // Try string lookup
    if (typeof rawReason === 'string') {
      return FINISH_REASON_MAP[rawReason] ?? rawReason;
    }

    // Try integer lookup
    if (typeof rawReason === 'number') {
      return FINISH_REASON_INT_MAP[rawReason] ?? String(rawReason);
    }

    return String(rawReason);
  }

  private buildErrorData(error: Error): ErrorData {
    const errorType = error.constructor.name;
    const errorMessage = error.message;

    // Try to extract error details
    let errorCode: string | undefined;
    const errorAny = error as {
      status_code?: number;
      statusCode?: number;
      code?: string;
      reason?: string;
      type?: string;
    };

    if (errorAny.status_code) {
      errorCode = String(errorAny.status_code);
    } else if (errorAny.statusCode) {
      errorCode = String(errorAny.statusCode);
    } else if (errorAny.code) {
      errorCode = String(errorAny.code);
    } else if (errorAny.reason) {
      errorCode = String(errorAny.reason);
    } else if (errorAny.type) {
      errorCode = String(errorAny.type);
    }

    return {
      type: errorType,
      message: errorMessage,
      code: errorCode,
    };
  }
}

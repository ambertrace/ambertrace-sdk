/**
 * Trace collection and serialization for OpenAI.
 */

import type { BaseCollector } from '../base';
import type { Trace, RequestData, ResponseData, ErrorData } from '../../models';
import { getConfig } from '../../config';
import { VERSION } from '../../version';

/**
 * Collects and builds trace objects from OpenAI API calls.
 */
export class OpenAICollector implements BaseCollector {
  getProviderName(): string {
    return 'openai';
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
      const requestData = this.buildRequestData(requestArgs);

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
        provider: 'openai',
        method: 'chat.completions.create',
        duration_ms: durationMs,
        request: requestData,
        response: responseData,
        error: errorData,
        sdk_version: `ambertrace-node/${VERSION}`,
        environment,
      };

      if (config?.debug) {
        console.log(`[AmberTrace] Collected OpenAI trace ${traceId} (duration: ${durationMs.toFixed(2)}ms)`);
      }

      return trace;
    } catch (err) {
      // Never raise exceptions - log and return null
      console.error(`[AmberTrace] Failed to collect OpenAI trace ${traceId}:`, err);
      return null;
    }
  }

  private buildRequestData(args: Record<string, unknown>): RequestData {
    // Extract model
    const model = (args.model as string) ?? 'unknown';

    // Extract messages
    const rawMessages = (args.messages as Array<{ role: string; content: string }>) ?? [];
    const messages = rawMessages.map((msg) => ({
      role: msg.role ?? 'unknown',
      content: String(msg.content ?? ''),
    }));

    // Extract parameters (exclude model and messages)
    const parameters: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(args)) {
      if (key !== 'model' && key !== 'messages') {
        parameters[key] = value;
      }
    }

    return {
      model,
      messages,
      parameters,
    };
  }

  private buildResponseData(response: unknown): ResponseData {
    const resp = response as {
      id?: string;
      model?: string;
      choices?: Array<{
        index?: number;
        message?: { role?: string; content?: string };
        finish_reason?: string;
      }>;
      usage?: {
        prompt_tokens?: number;
        completion_tokens?: number;
        total_tokens?: number;
      };
    };

    // Extract response ID
    const id = resp.id ?? 'unknown';

    // Extract model
    const model = resp.model ?? 'unknown';

    // Extract choices
    const rawChoices = resp.choices ?? [];
    const choices = rawChoices.map((choice) => ({
      index: choice.index ?? 0,
      message: {
        role: choice.message?.role ?? 'assistant',
        content: choice.message?.content ?? '',
      },
      finish_reason: choice.finish_reason ?? 'unknown',
    }));

    // Extract usage
    const usage = {
      prompt_tokens: resp.usage?.prompt_tokens ?? 0,
      completion_tokens: resp.usage?.completion_tokens ?? 0,
      total_tokens: resp.usage?.total_tokens ?? 0,
    };

    return {
      id,
      model,
      choices,
      usage,
    };
  }

  private buildErrorData(error: Error): ErrorData {
    const errorType = error.constructor.name;
    const errorMessage = error.message;

    // Try to extract OpenAI error code
    let errorCode: string | undefined;
    const errorAny = error as { code?: string; status?: number; type?: string };

    if (errorAny.code) {
      errorCode = String(errorAny.code);
    } else if (errorAny.status) {
      errorCode = String(errorAny.status);
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

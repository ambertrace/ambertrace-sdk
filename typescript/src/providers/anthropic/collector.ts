/**
 * Trace collection and serialization for Anthropic Claude.
 *
 * Normalizes Anthropic-specific format to match unified trace structure:
 * - system parameter → prepended as system message
 * - input_tokens → prompt_tokens
 * - output_tokens → completion_tokens
 * - Content blocks (list) → flattened string
 * - stop_reason → finish_reason with mapping
 */

import type { BaseCollector } from '../base';
import type { Trace, RequestData, ResponseData, ErrorData, Message } from '../../models';
import { getConfig } from '../../config';
import { VERSION } from '../../version';

/**
 * Collects and builds trace objects from Anthropic API calls.
 */
export class AnthropicCollector implements BaseCollector {
  getProviderName(): string {
    return 'anthropic';
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
        provider: 'anthropic',
        method: 'messages.create',
        duration_ms: durationMs,
        request: requestData,
        response: responseData,
        error: errorData,
        sdk_version: `ambertrace-node/${VERSION}`,
        environment,
      };

      if (config?.debug) {
        console.log(
          `[AmberTrace] Collected Anthropic trace ${traceId} (duration: ${durationMs.toFixed(2)}ms)`
        );
      }

      return trace;
    } catch (err) {
      // Never raise exceptions - log and return null
      console.error(`[AmberTrace] Failed to collect Anthropic trace ${traceId}:`, err);
      return null;
    }
  }

  private buildRequestData(args: Record<string, unknown>): RequestData {
    // Extract model
    const model = (args.model as string) ?? 'unknown';

    // Extract messages
    const rawMessages = (args.messages as Array<{ role: string; content: unknown }>) ?? [];
    const messages: Message[] = [];

    // Anthropic has a separate 'system' parameter
    // Prepend it as a system message for consistency with OpenAI format
    const system = args.system;
    if (system) {
      messages.push({
        role: 'system',
        content: String(system),
      });
    }

    // Process messages
    for (const msg of rawMessages) {
      const role = msg.role ?? 'unknown';
      let content = msg.content;

      // Anthropic content can be a string or array of content blocks
      if (Array.isArray(content)) {
        // Join text blocks into single string
        const textParts: string[] = [];
        for (const block of content) {
          if (
            typeof block === 'object' &&
            block !== null &&
            'type' in block &&
            block.type === 'text' &&
            'text' in block
          ) {
            textParts.push(String(block.text));
          }
        }
        content = textParts.join(' ');
      }

      messages.push({
        role,
        content: String(content ?? ''),
      });
    }

    // Extract parameters (exclude model, messages, and system)
    const parameters: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(args)) {
      if (key !== 'model' && key !== 'messages' && key !== 'system') {
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
      content?: Array<{ type?: string; text?: string }>;
      stop_reason?: string;
      usage?: {
        input_tokens?: number;
        output_tokens?: number;
      };
    };

    // Extract response ID
    const id = resp.id ?? 'unknown';

    // Extract model
    const model = resp.model ?? 'unknown';

    // Extract content blocks and flatten to string
    const contentBlocks = resp.content ?? [];
    let assistantMessage = '';
    for (const block of contentBlocks) {
      if (block.type === 'text' && block.text) {
        assistantMessage += block.text;
      }
    }

    // Map Anthropic's stop_reason to OpenAI's finish_reason
    const stopReason = resp.stop_reason ?? 'unknown';
    const finishReasonMap: Record<string, string> = {
      end_turn: 'stop',
      max_tokens: 'length',
      stop_sequence: 'stop',
    };
    const finishReason = finishReasonMap[stopReason] ?? stopReason;

    // Build choices array (Anthropic always has 1 choice)
    const choices = [
      {
        index: 0,
        message: {
          role: 'assistant',
          content: assistantMessage,
        },
        finish_reason: finishReason,
      },
    ];

    // Extract usage and normalize to OpenAI format
    const usage = resp.usage
      ? {
          prompt_tokens: resp.usage.input_tokens ?? 0, // input_tokens → prompt_tokens
          completion_tokens: resp.usage.output_tokens ?? 0, // output_tokens → completion_tokens
          total_tokens:
            (resp.usage.input_tokens ?? 0) + (resp.usage.output_tokens ?? 0), // Calculate total
        }
      : {
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: 0,
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

    // Try to extract Anthropic error details
    let errorCode: string | undefined;
    const errorAny = error as { status_code?: number; code?: string; type?: string };

    if (errorAny.status_code) {
      errorCode = String(errorAny.status_code);
    } else if (errorAny.code) {
      errorCode = String(errorAny.code);
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

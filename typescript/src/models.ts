/**
 * Core data models for AmberTrace TypeScript SDK.
 *
 * These models define the unified trace format used across all LLM providers.
 * The structure matches the Python SDK for backend compatibility.
 */

/**
 * A single message in a conversation.
 */
export interface Message {
  role: string;
  content: string;
}

/**
 * Request data sent to LLM provider.
 */
export interface RequestData {
  model: string;
  messages: Message[];
  parameters: Record<string, unknown>;
}

/**
 * A single choice/completion from the LLM response.
 */
export interface Choice {
  index: number;
  message: Message;
  finish_reason: string;
}

/**
 * Token usage statistics.
 */
export interface UsageData {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

/**
 * Successful response data from LLM provider.
 */
export interface ResponseData {
  id: string;
  model: string;
  choices: Choice[];
  usage: UsageData;
}

/**
 * Error data when LLM call fails.
 */
export interface ErrorData {
  type: string;
  message: string;
  code?: string;
}

/**
 * Complete trace object representing a single LLM API call.
 *
 * This is the unified format sent to AmberTrace backend,
 * regardless of which provider (OpenAI, Anthropic, etc.) was used.
 */
export interface Trace {
  trace_id: string;
  timestamp: string;
  provider: string;
  method: string;
  duration_ms: number;
  request: RequestData;
  response?: ResponseData;
  error?: ErrorData;
  sdk_version: string;
  environment?: string;
  service_name?: string;
  trace_session_id?: string;
}

/**
 * Serializes a trace object to JSON-compatible format.
 *
 * @param trace - The trace object to serialize
 * @returns JSON-serializable object
 */
export function serializeTrace(trace: Trace): Record<string, unknown> {
  return {
    trace_id: trace.trace_id,
    timestamp: trace.timestamp,
    provider: trace.provider,
    method: trace.method,
    duration_ms: trace.duration_ms,
    request: trace.request,
    response: trace.response ?? null,
    error: trace.error ?? null,
    sdk_version: trace.sdk_version,
    environment: trace.environment ?? null,
    service_name: trace.service_name ?? null,
    trace_session_id: trace.trace_session_id ?? null,
  };
}

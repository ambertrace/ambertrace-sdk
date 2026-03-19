package dev.ambertrace.providers;

import dev.ambertrace.Config;
import dev.ambertrace.Version;
import dev.ambertrace.models.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Base class for provider-specific trace collectors.
 *
 * <p>Each provider implements {@link #collectTrace} to extract data from their
 * specific response formats. The shared {@link #buildTrace} method handles
 * dataclass creation and serialization.
 */
public abstract class BaseCollector {

    private static final Logger logger = LoggerFactory.getLogger(BaseCollector.class);

    /**
     * Collect and serialize a trace from an LLM API call.
     *
     * <p>Must NEVER throw. Returns null on failure.
     *
     * @param traceId unique trace ID (UUID)
     * @param startTimeNanos start time from {@code System.nanoTime()}
     * @param requestParams provider-specific request parameters
     * @param response provider response object, or null if failed
     * @param error exception, or null if successful
     * @return serialized trace map, or null
     */
    public abstract Map<String, Object> collectTrace(
        String traceId,
        long startTimeNanos,
        Object requestParams,
        Object response,
        Exception error
    );

    /** Return the provider name (e.g., "openai", "anthropic", "gemini"). */
    public abstract String getProviderName();

    /**
     * Build a trace from normalized data and serialize it.
     *
     * @param traceId unique trace ID
     * @param timestamp ISO 8601 timestamp
     * @param provider provider name
     * @param method API method name
     * @param durationMs call duration in milliseconds
     * @param requestData normalized request data map
     * @param responseData normalized response data map (nullable)
     * @param errorData normalized error data map (nullable)
     * @return serialized trace map, or null on failure
     */
    @SuppressWarnings("unchecked")
    protected Map<String, Object> buildTrace(
        String traceId,
        String timestamp,
        String provider,
        String method,
        double durationMs,
        Map<String, Object> requestData,
        Map<String, Object> responseData,
        Map<String, Object> errorData
    ) {
        try {
            // Build request
            List<Message> messages = new ArrayList<>();
            Object rawMsgs = requestData.get("messages");
            if (rawMsgs instanceof List) {
                for (Object m : (List<?>) rawMsgs) {
                    if (m instanceof Map) {
                        Map<String, Object> mm = (Map<String, Object>) m;
                        messages.add(new Message(
                            String.valueOf(mm.getOrDefault("role", "unknown")),
                            String.valueOf(mm.getOrDefault("content", ""))
                        ));
                    }
                }
            }

            Object rawParams = requestData.get("parameters");
            Map<String, Object> parameters = (rawParams instanceof Map)
                ? (Map<String, Object>) rawParams
                : new LinkedHashMap<>();

            RequestData request = new RequestData(
                String.valueOf(requestData.getOrDefault("model", "unknown")),
                messages,
                parameters
            );

            // Build response (optional)
            ResponseData response = null;
            if (responseData != null) {
                List<Choice> choices = new ArrayList<>();
                Object rawChoices = responseData.get("choices");
                if (rawChoices instanceof List) {
                    for (Object c : (List<?>) rawChoices) {
                        if (c instanceof Map) {
                            Map<String, Object> cm = (Map<String, Object>) c;
                            Object msgObj = cm.get("message");
                            Message msg = new Message("assistant", "");
                            if (msgObj instanceof Map) {
                                Map<String, Object> mm = (Map<String, Object>) msgObj;
                                msg = new Message(
                                    String.valueOf(mm.getOrDefault("role", "assistant")),
                                    String.valueOf(mm.getOrDefault("content", ""))
                                );
                            }
                            choices.add(new Choice(
                                toInt(cm.getOrDefault("index", 0)),
                                msg,
                                String.valueOf(cm.getOrDefault("finish_reason", "unknown"))
                            ));
                        }
                    }
                }

                Object rawUsage = responseData.get("usage");
                UsageData usage = new UsageData(0, 0, 0);
                if (rawUsage instanceof Map) {
                    Map<String, Object> um = (Map<String, Object>) rawUsage;
                    Integer cached = um.containsKey("cached_tokens") ? toIntOrNull(um.get("cached_tokens")) : null;
                    Integer reasoning = um.containsKey("reasoning_tokens") ? toIntOrNull(um.get("reasoning_tokens")) : null;
                    usage = new UsageData(
                        toInt(um.getOrDefault("prompt_tokens", 0)),
                        toInt(um.getOrDefault("completion_tokens", 0)),
                        toInt(um.getOrDefault("total_tokens", 0)),
                        cached,
                        reasoning
                    );
                }

                response = new ResponseData(
                    String.valueOf(responseData.getOrDefault("id", "unknown")),
                    String.valueOf(responseData.getOrDefault("model", "unknown")),
                    choices,
                    usage
                );
            }

            // Build error (optional)
            ErrorData error = null;
            if (errorData != null) {
                error = new ErrorData(
                    String.valueOf(errorData.getOrDefault("type", "unknown")),
                    String.valueOf(errorData.getOrDefault("message", "")),
                    errorData.get("code") != null ? String.valueOf(errorData.get("code")) : null
                );
            }

            // Get environment from config
            Config config = Config.get();
            String environment = config != null ? config.getEnvironment() : null;

            Trace trace = Trace.builder()
                .traceId(traceId)
                .timestamp(timestamp)
                .provider(provider)
                .method(method)
                .durationMs(durationMs)
                .request(request)
                .response(response)
                .error(error)
                .sdkVersion("java/" + Version.VERSION)
                .environment(environment)
                .serviceName(config != null ? config.getServiceName() : null)
                .traceSessionId(config != null ? config.getTraceSessionId() : null)
                .build();

            return trace.toMap();

        } catch (Exception e) {
            logger.error("Failed to build trace {}: {}", traceId, e.getMessage(), e);
            return null;
        }
    }

    private static int toInt(Object value) {
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private static Integer toIntOrNull(Object value) {
        if (value == null) return null;
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (NumberFormatException e) {
            return null;
        }
    }
}

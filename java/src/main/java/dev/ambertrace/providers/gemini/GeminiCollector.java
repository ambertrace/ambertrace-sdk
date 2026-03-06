package dev.ambertrace.providers.gemini;

import dev.ambertrace.providers.BaseCollector;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Instant;
import java.util.*;

/**
 * Collector for Google Gemini API traces.
 *
 * <p>Extracts data from Gemini SDK's request/response objects
 * into the normalized trace format.
 */
public class GeminiCollector extends BaseCollector {

    private static final Logger logger = LoggerFactory.getLogger(GeminiCollector.class);

    @Override
    public String getProviderName() {
        return "gemini";
    }

    @Override
    public Map<String, Object> collectTrace(
        String traceId,
        long startTimeNanos,
        Object requestParams,
        Object response,
        Exception error
    ) {
        try {
            double durationMs = (System.nanoTime() - startTimeNanos) / 1_000_000.0;
            String timestamp = Instant.now().toString();

            Map<String, Object> requestData = buildRequestData(requestParams);
            Map<String, Object> responseData = response != null ? buildResponseData(response) : null;
            Map<String, Object> errorData = error != null ? buildErrorData(error) : null;

            return buildTrace(
                traceId, timestamp, "gemini", "models.generateContent",
                durationMs, requestData, responseData, errorData
            );
        } catch (Exception e) {
            logger.error("Failed to collect Gemini trace: {}", e.getMessage(), e);
            return null;
        }
    }

    /**
     * Build request data from Gemini call parameters.
     *
     * <p>requestParams is expected to be a {@code GeminiRequestContext} map
     * containing "model", "content", and optionally "config".
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> buildRequestData(Object requestParams) {
        Map<String, Object> data = new LinkedHashMap<>();
        if (requestParams instanceof Map) {
            Map<String, Object> ctx = (Map<String, Object>) requestParams;
            data.put("model", ctx.getOrDefault("model", "unknown"));

            // Convert content to messages format
            List<Map<String, Object>> messages = new ArrayList<>();
            Object content = ctx.get("content");
            if (content instanceof String) {
                Map<String, Object> msg = new LinkedHashMap<>();
                msg.put("role", "user");
                msg.put("content", content);
                messages.add(msg);
            }
            data.put("messages", messages);

            // Extract config as parameters
            Map<String, Object> params = new LinkedHashMap<>();
            Object config = ctx.get("config");
            if (config != null) {
                extractOptional(config, "temperature", params);
                extractOptional(config, "topP", params);
                extractOptional(config, "topK", params);
                extractOptional(config, "maxOutputTokens", params);
            }
            data.put("parameters", params);
        } else {
            data.put("model", "unknown");
            data.put("messages", Collections.emptyList());
            data.put("parameters", Collections.emptyMap());
        }
        return data;
    }

    private Map<String, Object> buildResponseData(Object response) {
        Map<String, Object> data = new LinkedHashMap<>();

        try {
            data.put("id", "gemini-" + UUID.randomUUID().toString().substring(0, 8));

            // Try to get model from response or fallback
            data.put("model", "unknown");

            // Extract text via response.text()
            List<Map<String, Object>> choices = new ArrayList<>();
            Object text = invoke(response, "text");
            String responseText = "";
            if (text instanceof String) {
                responseText = (String) text;
            }

            Map<String, Object> choiceMsg = new LinkedHashMap<>();
            choiceMsg.put("role", "assistant");
            choiceMsg.put("content", responseText);

            Map<String, Object> choice = new LinkedHashMap<>();
            choice.put("index", 0);
            choice.put("message", choiceMsg);
            choice.put("finish_reason", "stop");
            choices.add(choice);
            data.put("choices", choices);

            // Extract usage via usageMetadata()
            Map<String, Object> usage = new LinkedHashMap<>();
            Object usageMetadata = invoke(response, "usageMetadata");
            if (usageMetadata instanceof Optional) {
                Optional<?> optMeta = (Optional<?>) usageMetadata;
                if (optMeta.isPresent()) {
                    Object meta = optMeta.get();
                    int promptTokens = safeOptionalInt(meta, "promptTokenCount");
                    int completionTokens = safeOptionalInt(meta, "candidatesTokenCount");
                    int totalTokens = safeOptionalInt(meta, "totalTokenCount");
                    usage.put("prompt_tokens", promptTokens);
                    usage.put("completion_tokens", completionTokens);
                    usage.put("total_tokens", totalTokens);
                }
            }
            if (usage.isEmpty()) {
                usage.put("prompt_tokens", 0);
                usage.put("completion_tokens", 0);
                usage.put("total_tokens", 0);
            }
            data.put("usage", usage);

        } catch (Exception e) {
            logger.debug("Error extracting Gemini response data: {}", e.getMessage());
            data.putIfAbsent("id", "unknown");
            data.putIfAbsent("model", "unknown");
            data.putIfAbsent("choices", Collections.emptyList());
            data.putIfAbsent("usage", Map.of("prompt_tokens", 0, "completion_tokens", 0, "total_tokens", 0));
        }

        return data;
    }

    private Map<String, Object> buildErrorData(Exception error) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("type", error.getClass().getSimpleName());
        data.put("message", error.getMessage() != null ? error.getMessage() : "");
        return data;
    }

    /**
     * Get an Optional int field (returns 0 if absent or error).
     */
    @SuppressWarnings("unchecked")
    private int safeOptionalInt(Object obj, String methodName) {
        try {
            Object result = obj.getClass().getMethod(methodName).invoke(obj);
            if (result instanceof Optional) {
                return ((Optional<Integer>) result).orElse(0);
            }
            if (result instanceof Number) {
                return ((Number) result).intValue();
            }
        } catch (Exception ignored) {}
        return 0;
    }

    private void extractOptional(Object obj, String methodName, Map<String, Object> target) {
        try {
            Object value = invoke(obj, methodName);
            if (value instanceof Optional) {
                ((Optional<?>) value).ifPresent(v -> target.put(toSnakeCase(methodName), v));
            } else if (value != null) {
                target.put(toSnakeCase(methodName), value);
            }
        } catch (Exception ignored) {}
    }

    private static Object invoke(Object obj, String methodName) {
        try {
            return obj.getClass().getMethod(methodName).invoke(obj);
        } catch (Exception e) {
            return null;
        }
    }

    private static String toSnakeCase(String camelCase) {
        return camelCase.replaceAll("([a-z])([A-Z])", "$1_$2").toLowerCase();
    }
}

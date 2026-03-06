package dev.ambertrace.providers.openai;

import dev.ambertrace.providers.BaseCollector;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Instant;
import java.util.*;

/**
 * Collector for OpenAI chat completion traces.
 *
 * <p>Extracts data from {@code ChatCompletionCreateParams} and {@code ChatCompletion}
 * into the normalized trace format.
 */
public class OpenAICollector extends BaseCollector {

    private static final Logger logger = LoggerFactory.getLogger(OpenAICollector.class);

    @Override
    public String getProviderName() {
        return "openai";
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
                traceId, timestamp, "openai", "chat.completions.create",
                durationMs, requestData, responseData, errorData
            );
        } catch (Exception e) {
            logger.error("Failed to collect OpenAI trace: {}", e.getMessage(), e);
            return null;
        }
    }

    private Map<String, Object> buildRequestData(Object requestParams) {
        Map<String, Object> data = new LinkedHashMap<>();
        if (requestParams == null) {
            data.put("model", "unknown");
            data.put("messages", Collections.emptyList());
            data.put("parameters", Collections.emptyMap());
            return data;
        }

        try {
            // com.openai.models.chat.completions.ChatCompletionCreateParams
            Object model = invoke(requestParams, "model");
            data.put("model", model != null ? model.toString() : "unknown");

            // Extract messages
            List<Map<String, Object>> messages = new ArrayList<>();
            Object msgList = invoke(requestParams, "messages");
            if (msgList instanceof Iterable) {
                for (Object msg : (Iterable<?>) msgList) {
                    messages.add(extractMessage(msg));
                }
            }
            data.put("messages", messages);

            // Extract parameters (temperature, maxCompletionTokens, etc.)
            Map<String, Object> params = new LinkedHashMap<>();
            extractOptional(requestParams, "temperature", params);
            extractOptional(requestParams, "topP", params);
            extractOptional(requestParams, "n", params);
            extractOptional(requestParams, "maxCompletionTokens", params);
            data.put("parameters", params);

        } catch (Exception e) {
            logger.debug("Error extracting OpenAI request data: {}", e.getMessage());
            data.putIfAbsent("model", "unknown");
            data.putIfAbsent("messages", Collections.emptyList());
            data.putIfAbsent("parameters", Collections.emptyMap());
        }

        return data;
    }

    private Map<String, Object> buildResponseData(Object response) {
        Map<String, Object> data = new LinkedHashMap<>();

        try {
            // com.openai.models.chat.completions.ChatCompletion
            data.put("id", safeInvoke(response, "id", "unknown"));
            data.put("model", safeInvoke(response, "model", "unknown"));

            // Extract choices
            List<Map<String, Object>> choices = new ArrayList<>();
            Object choiceList = invoke(response, "choices");
            if (choiceList instanceof Iterable) {
                int idx = 0;
                for (Object choice : (Iterable<?>) choiceList) {
                    Map<String, Object> choiceMap = new LinkedHashMap<>();
                    choiceMap.put("index", idx++);

                    Object finishReason = invoke(choice, "finishReason");
                    choiceMap.put("finish_reason", finishReason != null ? finishReason.toString() : "unknown");

                    Object message = invoke(choice, "message");
                    Map<String, Object> msgMap = new LinkedHashMap<>();
                    msgMap.put("role", "assistant");
                    if (message != null) {
                        Object content = invoke(message, "content");
                        // content() returns Optional<String>
                        if (content instanceof Optional) {
                            Object val = ((Optional<?>) content).orElse(null);
                            msgMap.put("content", val != null ? val.toString() : "");
                        } else {
                            msgMap.put("content", content != null ? content.toString() : "");
                        }
                    } else {
                        msgMap.put("content", "");
                    }
                    choiceMap.put("message", msgMap);
                    choices.add(choiceMap);
                }
            }
            data.put("choices", choices);

            // Extract usage
            Map<String, Object> usage = new LinkedHashMap<>();
            Object usageObj = invoke(response, "usage");
            // usage() returns Optional<CompletionUsage>
            if (usageObj instanceof Optional) {
                Optional<?> optUsage = (Optional<?>) usageObj;
                if (optUsage.isPresent()) {
                    Object u = optUsage.get();
                    usage.put("prompt_tokens", safeInvokeLong(u, "promptTokens", 0));
                    usage.put("completion_tokens", safeInvokeLong(u, "completionTokens", 0));
                    usage.put("total_tokens", safeInvokeLong(u, "totalTokens", 0));
                }
            }
            if (usage.isEmpty()) {
                usage.put("prompt_tokens", 0);
                usage.put("completion_tokens", 0);
                usage.put("total_tokens", 0);
            }
            data.put("usage", usage);

        } catch (Exception e) {
            logger.debug("Error extracting OpenAI response data: {}", e.getMessage());
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

        // Try to get error code from OpenAI exceptions
        String code = null;
        try {
            Object statusCode = invoke(error, "statusCode");
            if (statusCode != null) {
                code = statusCode.toString();
            }
        } catch (Exception ignored) {}

        if (code != null) {
            data.put("code", code);
        }
        return data;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> extractMessage(Object msg) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            // ChatCompletionMessageParam is a sealed interface with variants
            // Try to get role and content via reflection
            Object role = safeInvoke(msg, "role", "unknown");
            result.put("role", role.toString().toLowerCase());

            Object content = invoke(msg, "content");
            if (content instanceof Optional) {
                Object optVal = ((Optional<?>) content).orElse(null);
                content = optVal != null ? optVal : "";
            }
            if (content instanceof String) {
                result.put("content", content);
            } else {
                // Could be a list of content parts — stringify
                result.put("content", content != null ? content.toString() : "");
            }
        } catch (Exception e) {
            result.putIfAbsent("role", "unknown");
            result.putIfAbsent("content", "");
        }
        return result;
    }

    private void extractOptional(Object obj, String methodName, Map<String, Object> target) {
        try {
            Object value = invoke(obj, methodName);
            if (value instanceof Optional) {
                Optional<?> opt = (Optional<?>) value;
                opt.ifPresent(v -> target.put(toSnakeCase(methodName), v));
            } else if (value != null) {
                target.put(toSnakeCase(methodName), value);
            }
        } catch (Exception ignored) {}
    }

    // --- Reflection helpers ---

    private static Object invoke(Object obj, String methodName) {
        try {
            return obj.getClass().getMethod(methodName).invoke(obj);
        } catch (Exception e) {
            return null;
        }
    }

    private static Object safeInvoke(Object obj, String methodName, Object fallback) {
        Object result = invoke(obj, methodName);
        return result != null ? result : fallback;
    }

    private static int safeInvokeLong(Object obj, String methodName, int fallback) {
        try {
            Object result = obj.getClass().getMethod(methodName).invoke(obj);
            if (result instanceof Number) {
                return ((Number) result).intValue();
            }
        } catch (Exception ignored) {}
        return fallback;
    }

    private static String toSnakeCase(String camelCase) {
        return camelCase.replaceAll("([a-z])([A-Z])", "$1_$2").toLowerCase();
    }
}

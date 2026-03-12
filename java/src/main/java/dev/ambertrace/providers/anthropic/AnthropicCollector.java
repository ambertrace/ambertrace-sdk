package dev.ambertrace.providers.anthropic;

import dev.ambertrace.providers.BaseCollector;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Instant;
import java.util.*;

/**
 * Collector for Anthropic Messages API traces.
 *
 * <p>Extracts data from {@code MessageCreateParams} and {@code Message}
 * into the normalized trace format.
 */
public class AnthropicCollector extends BaseCollector {

    private static final Logger logger = LoggerFactory.getLogger(AnthropicCollector.class);

    @Override
    public String getProviderName() {
        return "anthropic";
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
                traceId, timestamp, "anthropic", "messages.create",
                durationMs, requestData, responseData, errorData
            );
        } catch (Exception e) {
            logger.error("Failed to collect Anthropic trace: {}", e.getMessage(), e);
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
            Object model = invoke(requestParams, "model");
            if (model != null) {
                Object asStr = invoke(model, "asString");
                data.put("model", asStr != null ? asStr.toString() : model.toString());
            } else {
                data.put("model", "unknown");
            }

            // Extract messages
            List<Map<String, Object>> messages = new ArrayList<>();
            Object msgList = invoke(requestParams, "messages");
            if (msgList instanceof Iterable) {
                for (Object msg : (Iterable<?>) msgList) {
                    messages.add(extractMessage(msg));
                }
            }
            data.put("messages", messages);

            // Extract parameters
            Map<String, Object> params = new LinkedHashMap<>();
            extractOptional(requestParams, "maxTokens", params);
            extractOptional(requestParams, "temperature", params);
            extractOptional(requestParams, "topK", params);
            extractOptional(requestParams, "topP", params);
            data.put("parameters", params);

        } catch (Exception e) {
            logger.debug("Error extracting Anthropic request data: {}", e.getMessage());
            data.putIfAbsent("model", "unknown");
            data.putIfAbsent("messages", Collections.emptyList());
            data.putIfAbsent("parameters", Collections.emptyMap());
        }

        return data;
    }

    private Map<String, Object> buildResponseData(Object response) {
        Map<String, Object> data = new LinkedHashMap<>();

        try {
            data.put("id", safeInvoke(response, "id", "unknown"));

            Object model = invoke(response, "model");
            if (model != null) {
                Object asStr = invoke(model, "asString");
                data.put("model", asStr != null ? asStr.toString() : model.toString());
            } else {
                data.put("model", "unknown");
            }

            // Extract content blocks — choices
            List<Map<String, Object>> choices = new ArrayList<>();
            Object contentList = invoke(response, "content");
            if (contentList instanceof Iterable) {
                StringBuilder textContent = new StringBuilder();
                for (Object block : (Iterable<?>) contentList) {
                    // Check if it's a text block
                    try {
                        Object isText = invoke(block, "isText");
                        if (Boolean.TRUE.equals(isText)) {
                            Object textBlock = invoke(block, "asText");
                            if (textBlock != null) {
                                Object text = invoke(textBlock, "text");
                                if (text != null) {
                                    textContent.append(text.toString());
                                }
                            }
                        }
                    } catch (Exception ignored) {
                        // Try direct text() method
                        Object text = invoke(block, "text");
                        if (text instanceof Optional) {
                            ((Optional<?>) text).ifPresent(t -> textContent.append(t.toString()));
                        }
                    }
                }

                Map<String, Object> choiceMsg = new LinkedHashMap<>();
                choiceMsg.put("role", "assistant");
                choiceMsg.put("content", textContent.toString());

                Map<String, Object> choice = new LinkedHashMap<>();
                choice.put("index", 0);
                choice.put("message", choiceMsg);

                Object stopReason = invoke(response, "stopReason");
                if (stopReason instanceof Optional) {
                    Optional<?> optStop = (Optional<?>) stopReason;
                    if (optStop.isPresent()) {
                        Object sr = optStop.get();
                        Object asStr = invoke(sr, "asString");
                        choice.put("finish_reason", asStr != null ? asStr.toString() : sr.toString());
                    } else {
                        choice.put("finish_reason", "unknown");
                    }
                } else {
                    choice.put("finish_reason", stopReason != null ? stopReason.toString() : "unknown");
                }
                choices.add(choice);
            }
            data.put("choices", choices);

            // Extract usage: inputTokens → prompt_tokens, outputTokens → completion_tokens
            Map<String, Object> usage = new LinkedHashMap<>();
            Object usageObj = invoke(response, "usage");
            if (usageObj != null) {
                int inputTokens = safeInvokeLong(usageObj, "inputTokens", 0);
                int outputTokens = safeInvokeLong(usageObj, "outputTokens", 0);
                usage.put("prompt_tokens", inputTokens);
                usage.put("completion_tokens", outputTokens);
                usage.put("total_tokens", inputTokens + outputTokens);

                // Extract cached tokens from cacheReadInputTokens
                Integer cachedTokens = invokeOptionalLong(usageObj, "cacheReadInputTokens");
                if (cachedTokens != null) {
                    usage.put("cached_tokens", cachedTokens);
                }
            } else {
                usage.put("prompt_tokens", 0);
                usage.put("completion_tokens", 0);
                usage.put("total_tokens", 0);
            }
            data.put("usage", usage);

        } catch (Exception e) {
            logger.debug("Error extracting Anthropic response data: {}", e.getMessage());
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

    private Map<String, Object> extractMessage(Object msg) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            // MessageParam.role() returns Role (Enum) — use asString()
            Object role = invoke(msg, "role");
            if (role != null) {
                Object asStr = invoke(role, "asString");
                result.put("role", asStr != null ? asStr.toString().toLowerCase() : role.toString().toLowerCase());
            } else {
                result.put("role", "unknown");
            }

            // MessageParam.content() returns Content union: isString()/asString() or isBlockParams()/asBlockParams()
            Object content = invoke(msg, "content");
            if (content == null) {
                result.put("content", "");
            } else if (invokeBool(content, "isString")) {
                Object text = invoke(content, "asString");
                result.put("content", text != null ? text.toString() : "");
            } else if (invokeBool(content, "isBlockParams")) {
                Object blocks = invoke(content, "asBlockParams");
                if (blocks instanceof Iterable) {
                    StringBuilder sb = new StringBuilder();
                    for (Object block : (Iterable<?>) blocks) {
                        if (invokeBool(block, "isText")) {
                            Object textBlock = invoke(block, "asText");
                            if (textBlock != null) {
                                Object text = invoke(textBlock, "text");
                                if (text != null) sb.append(text.toString());
                            }
                        }
                    }
                    result.put("content", sb.toString());
                } else {
                    result.put("content", "");
                }
            } else {
                result.put("content", "");
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

    private static boolean invokeBool(Object obj, String methodName) {
        try {
            Object result = obj.getClass().getMethod(methodName).invoke(obj);
            return Boolean.TRUE.equals(result);
        } catch (Exception e) {
            return false;
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

    private static Integer invokeOptionalLong(Object obj, String methodName) {
        try {
            Object result = invoke(obj, methodName);
            if (result instanceof Optional) {
                Object val = ((Optional<?>) result).orElse(null);
                if (val instanceof Number) {
                    return ((Number) val).intValue();
                }
            }
        } catch (Exception ignored) {}
        return null;
    }

    private static String toSnakeCase(String camelCase) {
        return camelCase.replaceAll("([a-z])([A-Z])", "$1_$2").toLowerCase();
    }
}

package dev.ambertrace.providers.google;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.ambertrace.providers.BaseCollector;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Instant;
import java.util.*;

/**
 * Collector for Google Gemini API traces.
 *
 * <p>Extracts data from Gemini API request/response data into the normalized trace format.
 * Works with raw JSON request data from the {@link TracingApiClient} HTTP-level interception.
 */
public class GoogleCollector extends BaseCollector {

    private static final Logger logger = LoggerFactory.getLogger(GoogleCollector.class);
    private static final ObjectMapper mapper = new ObjectMapper();

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
            Map<String, Object> responseData = null;
            if (response instanceof String) {
                responseData = buildResponseData((String) response);
            }
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
     * Build request data from the request context map.
     *
     * <p>The context map from {@link TracingApiClient} contains:
     * <ul>
     *   <li>"model" — model name extracted from the API path</li>
     *   <li>"requestJson" — raw request JSON body</li>
     * </ul>
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> buildRequestData(Object requestParams) {
        Map<String, Object> data = new LinkedHashMap<>();
        if (requestParams instanceof Map) {
            Map<String, Object> ctx = (Map<String, Object>) requestParams;
            data.put("model", ctx.getOrDefault("model", "unknown"));

            // Try to parse messages from raw request JSON
            List<Map<String, Object>> messages = new ArrayList<>();
            Object requestJson = ctx.get("requestJson");
            if (requestJson instanceof String) {
                messages = parseMessagesFromJson((String) requestJson);
            }

            // Fallback: try legacy "content" key (for backward compatibility)
            if (messages.isEmpty()) {
                Object content = ctx.get("content");
                if (content instanceof String) {
                    Map<String, Object> msg = new LinkedHashMap<>();
                    msg.put("role", "user");
                    msg.put("content", content);
                    messages.add(msg);
                }
            }

            data.put("messages", messages);
            data.put("parameters", Collections.emptyMap());
        } else {
            data.put("model", "unknown");
            data.put("messages", Collections.emptyList());
            data.put("parameters", Collections.emptyMap());
        }
        return data;
    }

    /**
     * Parse messages from the raw Gemini request JSON.
     * The Gemini API format has a "contents" array with "parts" containing "text".
     */
    private List<Map<String, Object>> parseMessagesFromJson(String json) {
        List<Map<String, Object>> messages = new ArrayList<>();
        try {
            JsonNode root = mapper.readTree(json);
            JsonNode contents = root.get("contents");
            if (contents != null && contents.isArray()) {
                for (JsonNode content : contents) {
                    String role = content.has("role") ? content.get("role").asText() : "user";
                    JsonNode parts = content.get("parts");
                    if (parts != null && parts.isArray()) {
                        StringBuilder text = new StringBuilder();
                        for (JsonNode part : parts) {
                            if (part.has("text")) {
                                if (text.length() > 0) text.append("\n");
                                text.append(part.get("text").asText());
                            }
                        }
                        if (text.length() > 0) {
                            Map<String, Object> msg = new LinkedHashMap<>();
                            msg.put("role", role);
                            msg.put("content", text.toString());
                            messages.add(msg);
                        }
                    }
                }
            }
        } catch (Exception e) {
            logger.debug("Could not parse Gemini request JSON: {}", e.getMessage());
        }
        return messages;
    }

    /**
     * Build response data from the raw Gemini response JSON.
     *
     * <p>Extracts candidates (choices), usage metadata (token counts), and model info
     * from the Gemini API JSON response format.
     */
    private Map<String, Object> buildResponseData(String responseJson) {
        Map<String, Object> data = new LinkedHashMap<>();
        try {
            JsonNode root = mapper.readTree(responseJson);

            // Response ID
            data.put("id", root.has("responseId") ? root.get("responseId").asText() : "unknown");

            // Model version
            data.put("model", root.has("modelVersion") ? root.get("modelVersion").asText() : "unknown");

            // Extract candidates — choices
            List<Map<String, Object>> choices = new ArrayList<>();
            JsonNode candidates = root.get("candidates");
            if (candidates != null && candidates.isArray()) {
                for (int i = 0; i < candidates.size(); i++) {
                    JsonNode candidate = candidates.get(i);
                    Map<String, Object> choice = new LinkedHashMap<>();
                    choice.put("index", i);

                    // Extract text from candidate.content.parts
                    String text = extractCandidateText(candidate);
                    Map<String, Object> message = new LinkedHashMap<>();
                    message.put("role", "assistant");
                    message.put("content", text);
                    choice.put("message", message);

                    // Finish reason
                    String finishReason = candidate.has("finishReason")
                        ? normalizeFinishReason(candidate.get("finishReason").asText())
                        : "stop";
                    choice.put("finish_reason", finishReason);

                    choices.add(choice);
                }
            }
            data.put("choices", choices);

            // Extract usage metadata
            Map<String, Object> usage = new LinkedHashMap<>();
            JsonNode usageMeta = root.get("usageMetadata");
            if (usageMeta != null) {
                int promptTokens = usageMeta.has("promptTokenCount")
                    ? usageMeta.get("promptTokenCount").asInt(0) : 0;
                int completionTokens = usageMeta.has("candidatesTokenCount")
                    ? usageMeta.get("candidatesTokenCount").asInt(0) : 0;
                int totalTokens = usageMeta.has("totalTokenCount")
                    ? usageMeta.get("totalTokenCount").asInt(0) : 0;
                usage.put("prompt_tokens", promptTokens);
                usage.put("completion_tokens", completionTokens);
                usage.put("total_tokens", totalTokens);

                // Cached tokens
                if (usageMeta.has("cachedContentTokenCount")) {
                    usage.put("cached_tokens", usageMeta.get("cachedContentTokenCount").asInt(0));
                }
            } else {
                usage.put("prompt_tokens", 0);
                usage.put("completion_tokens", 0);
                usage.put("total_tokens", 0);
            }
            data.put("usage", usage);

        } catch (Exception e) {
            logger.debug("Could not parse Gemini response JSON: {}", e.getMessage());
            data.putIfAbsent("id", "unknown");
            data.putIfAbsent("model", "unknown");
            data.putIfAbsent("choices", Collections.emptyList());
            data.putIfAbsent("usage", Map.of("prompt_tokens", 0, "completion_tokens", 0, "total_tokens", 0));
        }
        return data;
    }

    /**
     * Extract text content from a candidate's content.parts array.
     */
    private String extractCandidateText(JsonNode candidate) {
        JsonNode content = candidate.get("content");
        if (content == null) return "";

        JsonNode parts = content.get("parts");
        if (parts == null || !parts.isArray()) return "";

        StringBuilder text = new StringBuilder();
        for (JsonNode part : parts) {
            if (part.has("text")) {
                if (text.length() > 0) text.append("\n");
                text.append(part.get("text").asText());
            }
        }
        return text.toString();
    }

    private static final Map<String, String> FINISH_REASON_MAP = Map.of(
        "STOP", "stop",
        "MAX_TOKENS", "length",
        "SAFETY", "content_filter",
        "RECITATION", "content_filter",
        "OTHER", "stop",
        "FINISH_REASON_UNSPECIFIED", "stop"
    );

    private String normalizeFinishReason(String raw) {
        return FINISH_REASON_MAP.getOrDefault(raw, "stop");
    }

    private Map<String, Object> buildErrorData(Exception error) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("type", error.getClass().getSimpleName());
        data.put("message", error.getMessage() != null ? error.getMessage() : "");
        return data;
    }
}

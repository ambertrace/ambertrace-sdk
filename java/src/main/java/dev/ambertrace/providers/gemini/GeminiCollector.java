package dev.ambertrace.providers.gemini;

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
public class GeminiCollector extends BaseCollector {

    private static final Logger logger = LoggerFactory.getLogger(GeminiCollector.class);
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
            Map<String, Object> responseData = null; // Response data captured at HTTP level is raw; skip for now
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

    private Map<String, Object> buildErrorData(Exception error) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("type", error.getClass().getSimpleName());
        data.put("message", error.getMessage() != null ? error.getMessage() : "");
        return data;
    }
}

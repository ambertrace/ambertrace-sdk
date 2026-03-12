package dev.ambertrace.providers;

import dev.ambertrace.Config;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class BaseCollectorTest {

    @BeforeEach
    void setup() {
        Config.set(Config.builder().apiKey("at_test").environment("test").build());
    }

    @AfterEach
    void cleanup() {
        Config.clear();
    }

    @Test
    void testBuildTraceSuccess() {
        TestCollector collector = new TestCollector();

        Map<String, Object> requestData = new LinkedHashMap<>();
        requestData.put("model", "gpt-4");
        requestData.put("messages", List.of(
            Map.of("role", "user", "content", "Hello")
        ));
        requestData.put("parameters", Map.of("temperature", 0.7));

        Map<String, Object> responseData = new LinkedHashMap<>();
        responseData.put("id", "chatcmpl-123");
        responseData.put("model", "gpt-4");
        responseData.put("choices", List.of(
            Map.of(
                "index", 0,
                "message", Map.of("role", "assistant", "content", "Hi!"),
                "finish_reason", "stop"
            )
        ));
        responseData.put("usage", Map.of(
            "prompt_tokens", 10,
            "completion_tokens", 5,
            "total_tokens", 15
        ));

        Map<String, Object> result = collector.buildTrace(
            "test-id", "2024-01-01T00:00:00Z", "openai",
            "chat.completions.create", 100.0,
            requestData, responseData, null
        );

        assertNotNull(result);
        assertEquals("test-id", result.get("trace_id"));
        assertEquals("openai", result.get("provider"));
        assertEquals("success", result.get("status"));
        assertEquals("gpt-4", result.get("request_model"));
        assertEquals(10, result.get("prompt_tokens"));
        assertEquals(5, result.get("completion_tokens"));
        assertEquals(15, result.get("total_tokens"));
        assertEquals("test", result.get("environment"));
    }

    @Test
    void testBuildTraceError() {
        TestCollector collector = new TestCollector();

        Map<String, Object> requestData = Map.of(
            "model", "gpt-4",
            "messages", List.of(Map.of("role", "user", "content", "Hello"))
        );

        Map<String, Object> errorData = Map.of(
            "type", "RateLimitError",
            "message", "Rate limit exceeded",
            "code", "429"
        );

        Map<String, Object> result = collector.buildTrace(
            "err-id", "2024-01-01T00:00:00Z", "openai",
            "chat.completions.create", 50.0,
            requestData, null, errorData
        );

        assertNotNull(result);
        assertEquals("error", result.get("status"));
        assertNull(result.get("response_data"));
        assertNotNull(result.get("error_data"));
    }

    @Test
    void testBuildTraceWithEmptyData() {
        TestCollector collector = new TestCollector();

        Map<String, Object> requestData = new LinkedHashMap<>();
        requestData.put("model", "unknown");
        requestData.put("messages", Collections.emptyList());

        Map<String, Object> result = collector.buildTrace(
            "empty-id", "2024-01-01T00:00:00Z", "openai",
            "chat.completions.create", 10.0,
            requestData, null, null
        );

        assertNotNull(result);
        assertEquals("success", result.get("status"));
        assertNull(result.get("prompt_tokens"));
    }

    static class TestCollector extends BaseCollector {
        @Override
        public Map<String, Object> collectTrace(String traceId, long startTimeNanos,
                                                  Object requestParams, Object response, Exception error) {
            return null; // Not used in this test
        }

        @Override
        public String getProviderName() {
            return "test";
        }

        // Expose protected method for testing
        @Override
        public Map<String, Object> buildTrace(String traceId, String timestamp, String provider,
                                               String method, double durationMs,
                                               Map<String, Object> requestData,
                                               Map<String, Object> responseData,
                                               Map<String, Object> errorData) {
            return super.buildTrace(traceId, timestamp, provider, method, durationMs,
                requestData, responseData, errorData);
        }
    }
}

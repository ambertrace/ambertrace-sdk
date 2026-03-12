package dev.ambertrace.models;

import org.junit.jupiter.api.Test;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class TraceTest {

    @Test
    void testSuccessTraceToMap() {
        RequestData request = new RequestData(
            "gpt-4",
            List.of(new Message("user", "Hello")),
            Map.of("temperature", 0.7)
        );

        ResponseData response = new ResponseData(
            "chatcmpl-123",
            "gpt-4",
            List.of(new Choice(0, new Message("assistant", "Hi there!"), "stop")),
            new UsageData(10, 20, 30)
        );

        Trace trace = Trace.builder()
            .traceId("test-trace-id")
            .timestamp("2024-01-01T00:00:00Z")
            .provider("openai")
            .method("chat.completions.create")
            .durationMs(150.5)
            .request(request)
            .response(response)
            .sdkVersion("ambertrace-java/0.1.0")
            .environment("test")
            .build();

        Map<String, Object> map = trace.toMap();

        assertEquals("test-trace-id", map.get("trace_id"));
        assertEquals("2024-01-01T00:00:00Z", map.get("timestamp"));
        assertEquals("openai", map.get("provider"));
        assertEquals("chat.completions.create", map.get("method"));
        assertEquals(150.5, map.get("duration_ms"));
        assertEquals("gpt-4", map.get("request_model"));
        assertEquals("success", map.get("status"));
        assertEquals("test", map.get("environment"));

        // Token counts at top level
        assertEquals(10, map.get("prompt_tokens"));
        assertEquals(20, map.get("completion_tokens"));
        assertEquals(30, map.get("total_tokens"));

        // Nested request_data
        @SuppressWarnings("unchecked")
        Map<String, Object> reqData = (Map<String, Object>) map.get("request_data");
        assertNotNull(reqData);
        assertEquals("gpt-4", reqData.get("model"));

        // Nested response_data
        @SuppressWarnings("unchecked")
        Map<String, Object> respData = (Map<String, Object>) map.get("response_data");
        assertNotNull(respData);
        assertEquals("chatcmpl-123", respData.get("id"));

        assertNull(map.get("error_data"));
    }

    @Test
    void testErrorTraceToMap() {
        RequestData request = new RequestData(
            "gpt-4",
            List.of(new Message("user", "Hello")),
            null
        );

        ErrorData error = new ErrorData("RateLimitError", "Rate limit exceeded", "429");

        Trace trace = Trace.builder()
            .traceId("error-trace-id")
            .timestamp("2024-01-01T00:00:00Z")
            .provider("openai")
            .method("chat.completions.create")
            .durationMs(50.0)
            .request(request)
            .error(error)
            .build();

        Map<String, Object> map = trace.toMap();

        assertEquals("error", map.get("status"));
        assertNull(map.get("response_data"));
        assertNull(map.get("prompt_tokens"));
        assertNull(map.get("completion_tokens"));
        assertNull(map.get("total_tokens"));

        @SuppressWarnings("unchecked")
        Map<String, Object> errorData = (Map<String, Object>) map.get("error_data");
        assertNotNull(errorData);
        assertEquals("RateLimitError", errorData.get("type"));
        assertEquals("Rate limit exceeded", errorData.get("message"));
        assertEquals("429", errorData.get("code"));
    }

    @Test
    void testMessageToMap() {
        Message msg = new Message("user", "Hello, world!");
        Map<String, Object> map = msg.toMap();

        assertEquals("user", map.get("role"));
        assertEquals("Hello, world!", map.get("content"));
    }

    @Test
    void testNullDefaults() {
        Message msg = new Message(null, null);
        assertEquals("unknown", msg.getRole());
        assertEquals("", msg.getContent());

        ErrorData error = new ErrorData(null, null, null);
        assertEquals("unknown", error.getType());
        assertEquals("", error.getMessage());
        assertNull(error.getCode());

        // ErrorData toMap should not include code when null
        Map<String, Object> errorMap = error.toMap();
        assertFalse(errorMap.containsKey("code"));
    }

    @Test
    void testUsageDataToMap() {
        UsageData usage = new UsageData(100, 200, 300);
        Map<String, Object> map = usage.toMap();

        assertEquals(100, map.get("prompt_tokens"));
        assertEquals(200, map.get("completion_tokens"));
        assertEquals(300, map.get("total_tokens"));
    }

    @Test
    void testChoiceToMap() {
        Choice choice = new Choice(0, new Message("assistant", "Hi"), "stop");
        Map<String, Object> map = choice.toMap();

        assertEquals(0, map.get("index"));
        assertEquals("stop", map.get("finish_reason"));

        @SuppressWarnings("unchecked")
        Map<String, Object> msgMap = (Map<String, Object>) map.get("message");
        assertEquals("assistant", msgMap.get("role"));
        assertEquals("Hi", msgMap.get("content"));
    }
}

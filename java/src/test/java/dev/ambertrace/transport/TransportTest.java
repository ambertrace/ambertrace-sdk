package dev.ambertrace.transport;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.ambertrace.Config;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;

class TransportTest {

    private MockWebServer server;
    private Transport transport;

    @BeforeEach
    void setup() throws Exception {
        server = new MockWebServer();
        server.start();

        String baseUrl = server.url("/").toString();
        // Remove trailing slash
        if (baseUrl.endsWith("/")) {
            baseUrl = baseUrl.substring(0, baseUrl.length() - 1);
        }

        Config config = Config.builder()
            .apiKey("at_test_key")
            .baseUrl(baseUrl)
            .timeoutMs(5000)
            .build();
        Config.set(config);

        transport = new Transport();
        transport.start();
        Transport.set(transport);
    }

    @AfterEach
    void cleanup() throws Exception {
        transport.stop();
        Transport.clear();
        Config.clear();
        server.shutdown();
    }

    @Test
    void testSendTraceSuccess() throws Exception {
        server.enqueue(new MockResponse().setResponseCode(201).setBody("{}"));

        Map<String, Object> trace = createTestTrace();
        transport.sendTrace(trace);
        transport.flush(5000);

        RecordedRequest request = server.takeRequest(5, TimeUnit.SECONDS);
        assertNotNull(request);
        assertEquals("POST", request.getMethod());
        assertEquals("/api/traces/ingest", request.getPath());
        assertEquals("Bearer at_test_key", request.getHeader("Authorization"));
        assertEquals("application/json", request.getHeader("Content-Type"));
        assertNotNull(request.getHeader("X-SDK-Version"));
        assertTrue(request.getHeader("X-SDK-Version").startsWith("ambertrace-java/"));

        // Verify JSON body
        String body = request.getBody().readUtf8();
        ObjectMapper mapper = new ObjectMapper();
        @SuppressWarnings("unchecked")
        Map<String, Object> parsed = mapper.readValue(body, Map.class);
        assertEquals("test-id", parsed.get("trace_id"));
    }

    @Test
    void testSendTraceServerError() throws Exception {
        server.enqueue(new MockResponse().setResponseCode(500).setBody("Internal Server Error"));

        Map<String, Object> trace = createTestTrace();
        transport.sendTrace(trace);
        transport.flush(5000);

        // Should not throw — errors are logged silently
        RecordedRequest request = server.takeRequest(5, TimeUnit.SECONDS);
        assertNotNull(request);
    }

    @Test
    void testDroppedCountWhenNotRunning() {
        Transport stoppedTransport = new Transport();
        // Don't start it
        stoppedTransport.sendTrace(createTestTrace());
        // Should not throw, trace is silently dropped
    }

    @Test
    void testFlushWithNoTraces() {
        // Should return immediately without error
        transport.flush(1000);
    }

    private Map<String, Object> createTestTrace() {
        Map<String, Object> trace = new LinkedHashMap<>();
        trace.put("trace_id", "test-id");
        trace.put("timestamp", "2024-01-01T00:00:00Z");
        trace.put("provider", "openai");
        trace.put("method", "chat.completions.create");
        trace.put("duration_ms", 100.0);
        trace.put("request_model", "gpt-4");
        trace.put("request_data", Map.of("model", "gpt-4"));
        trace.put("status", "success");
        return trace;
    }
}

package dev.ambertrace.models;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Main trace object containing all data for a single LLM API call.
 *
 * <p>{@link #toMap()} produces the flattened format matching the backend
 * {@code TraceCreate} schema, with token counts at the top level.
 */
public final class Trace {

    private final String traceId;
    private final String timestamp;
    private final String provider;
    private final String method;
    private final double durationMs;
    private final RequestData request;
    private final ResponseData response;
    private final ErrorData error;
    private final String sdkVersion;
    private final String environment;
    private final String serviceName;
    private final String traceSessionId;

    private Trace(Builder builder) {
        this.traceId = builder.traceId;
        this.timestamp = builder.timestamp;
        this.provider = builder.provider;
        this.method = builder.method;
        this.durationMs = builder.durationMs;
        this.request = builder.request;
        this.response = builder.response;
        this.error = builder.error;
        this.sdkVersion = builder.sdkVersion;
        this.environment = builder.environment;
        this.serviceName = builder.serviceName;
        this.traceSessionId = builder.traceSessionId;
    }

    public String getTraceId() { return traceId; }
    public String getTimestamp() { return timestamp; }
    public String getProvider() { return provider; }
    public String getMethod() { return method; }
    public double getDurationMs() { return durationMs; }
    public RequestData getRequest() { return request; }
    public ResponseData getResponse() { return response; }
    public ErrorData getError() { return error; }
    public String getSdkVersion() { return sdkVersion; }
    public String getEnvironment() { return environment; }
    public String getServiceName() { return serviceName; }
    public String getTraceSessionId() { return traceSessionId; }

    /**
     * Serialize to the flattened format matching backend {@code TraceCreate} schema.
     *
     * <p>Extracts token counts from response usage to top-level fields.
     * Sets {@code status} to "error" if error is present, "success" otherwise.
     */
    public Map<String, Object> toMap() {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("trace_id", traceId);
        map.put("timestamp", timestamp);
        map.put("provider", provider);
        map.put("method", method);
        map.put("duration_ms", durationMs);
        map.put("request_model", request.getModel());
        map.put("request_data", request.toMap());
        map.put("response_data", response != null ? response.toMap() : null);
        map.put("error_data", error != null ? error.toMap() : null);

        // Extract token counts
        Integer promptTokens = null;
        Integer completionTokens = null;
        Integer totalTokens = null;
        Integer cachedTokens = null;
        Integer reasoningTokens = null;
        if (response != null && response.getUsage() != null) {
            promptTokens = response.getUsage().getPromptTokens();
            completionTokens = response.getUsage().getCompletionTokens();
            totalTokens = response.getUsage().getTotalTokens();
            cachedTokens = response.getUsage().getCachedTokens();
            reasoningTokens = response.getUsage().getReasoningTokens();
        }
        map.put("prompt_tokens", promptTokens);
        map.put("completion_tokens", completionTokens);
        map.put("total_tokens", totalTokens);
        map.put("cached_tokens", cachedTokens);
        map.put("reasoning_tokens", reasoningTokens);

        map.put("status", error != null ? "error" : "success");
        map.put("environment", environment);
        map.put("service_name", serviceName);
        map.put("trace_session_id", traceSessionId);
        map.put("sdk_version", sdkVersion);

        return map;
    }

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private String traceId;
        private String timestamp;
        private String provider;
        private String method;
        private double durationMs;
        private RequestData request;
        private ResponseData response;
        private ErrorData error;
        private String sdkVersion;
        private String environment;
        private String serviceName;
        private String traceSessionId;

        private Builder() {}

        public Builder traceId(String traceId) { this.traceId = traceId; return this; }
        public Builder timestamp(String timestamp) { this.timestamp = timestamp; return this; }
        public Builder provider(String provider) { this.provider = provider; return this; }
        public Builder method(String method) { this.method = method; return this; }
        public Builder durationMs(double durationMs) { this.durationMs = durationMs; return this; }
        public Builder request(RequestData request) { this.request = request; return this; }
        public Builder response(ResponseData response) { this.response = response; return this; }
        public Builder error(ErrorData error) { this.error = error; return this; }
        public Builder sdkVersion(String sdkVersion) { this.sdkVersion = sdkVersion; return this; }
        public Builder environment(String environment) { this.environment = environment; return this; }
        public Builder serviceName(String serviceName) { this.serviceName = serviceName; return this; }
        public Builder traceSessionId(String traceSessionId) { this.traceSessionId = traceSessionId; return this; }

        public Trace build() {
            return new Trace(this);
        }
    }
}

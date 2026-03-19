package dev.ambertrace;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Configuration for the AmberTrace SDK.
 *
 * <p>Supports explicit values via the builder and environment variable fallbacks:
 * <ul>
 *   <li>{@code AMBERTRACE_API_KEY} — API key (required)</li>
 *   <li>{@code AMBERTRACE_BASE_URL} — Backend URL</li>
 *   <li>{@code AMBERTRACE_ENV} — Environment tag</li>
 *   <li>{@code AMBERTRACE_DEBUG} — Enable debug logging ("true")</li>
 *   <li>{@code AMBERTRACE_ENABLED} — Enable tracing ("true"/"false")</li>
 * </ul>
 */
public final class Config {

    private static final Logger logger = LoggerFactory.getLogger(Config.class);

    private static final String DEFAULT_BASE_URL = "https://api.ambertrace.dev";
    private static final long DEFAULT_TIMEOUT_MS = 5000;

    private final String apiKey;
    private final String baseUrl;
    private final String environment;
    private final boolean debug;
    private final long timeoutMs;
    private final boolean enabled;
    private final String serviceName;
    private volatile String traceSessionId;

    // Global singleton
    private static volatile Config instance;

    private Config(Builder builder) {
        this.apiKey = resolve(builder.apiKey, "AMBERTRACE_API_KEY", null);
        this.baseUrl = resolve(builder.baseUrl, "AMBERTRACE_BASE_URL", DEFAULT_BASE_URL);
        this.environment = resolve(builder.environment, "AMBERTRACE_ENV", null);
        this.debug = resolveBoolean(builder.debug, "AMBERTRACE_DEBUG", false);
        this.timeoutMs = builder.timeoutMs != null ? builder.timeoutMs : DEFAULT_TIMEOUT_MS;
        this.enabled = resolveBoolean(builder.enabled, "AMBERTRACE_ENABLED", true);
        this.serviceName = resolve(builder.serviceName, "AMBERTRACE_SERVICE_NAME", null);
        this.traceSessionId = SessionId.generate();

        if (this.apiKey == null || this.apiKey.isEmpty()) {
            throw new IllegalArgumentException(
                "AmberTrace API key is required. Pass it to Config.builder().apiKey(...) "
                + "or set the AMBERTRACE_API_KEY environment variable."
            );
        }
    }

    public String getApiKey() { return apiKey; }
    public String getBaseUrl() { return baseUrl; }
    public String getEnvironment() { return environment; }
    public boolean isDebug() { return debug; }
    public long getTimeoutMs() { return timeoutMs; }
    public boolean isEnabled() { return enabled; }
    public String getServiceName() { return serviceName; }
    public String getTraceSessionId() { return traceSessionId; }

    /** Rotate the trace session ID. Useful for long-running apps. */
    public String newSession() {
        this.traceSessionId = SessionId.generate();
        return this.traceSessionId;
    }

    public String getTracesEndpoint() {
        return baseUrl + "/api/traces/ingest";
    }

    public String getAuthHeader() {
        return "Bearer " + apiKey;
    }

    // --- Global singleton ---

    public static void set(Config config) {
        instance = config;
    }

    public static Config get() {
        return instance;
    }

    public static void clear() {
        instance = null;
    }

    // --- Builder ---

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private String apiKey;
        private String baseUrl;
        private String environment;
        private Boolean debug;
        private Long timeoutMs;
        private Boolean enabled;
        private String serviceName;

        private Builder() {}

        public Builder apiKey(String apiKey) { this.apiKey = apiKey; return this; }
        public Builder baseUrl(String baseUrl) { this.baseUrl = baseUrl; return this; }
        public Builder environment(String environment) { this.environment = environment; return this; }
        public Builder debug(boolean debug) { this.debug = debug; return this; }
        public Builder timeoutMs(long timeoutMs) { this.timeoutMs = timeoutMs; return this; }
        public Builder enabled(boolean enabled) { this.enabled = enabled; return this; }
        public Builder serviceName(String serviceName) { this.serviceName = serviceName; return this; }

        public Config build() {
            return new Config(this);
        }
    }

    // --- Helpers ---

    private static String resolve(String explicit, String envVar, String defaultValue) {
        if (explicit != null && !explicit.isEmpty()) {
            return explicit;
        }
        String envValue = System.getenv(envVar);
        if (envValue != null && !envValue.isEmpty()) {
            return envValue;
        }
        return defaultValue;
    }

    private static boolean resolveBoolean(Boolean explicit, String envVar, boolean defaultValue) {
        if (explicit != null) {
            return explicit;
        }
        String envValue = System.getenv(envVar);
        if (envValue != null && !envValue.isEmpty()) {
            return "true".equalsIgnoreCase(envValue) || "1".equals(envValue);
        }
        return defaultValue;
    }

    @Override
    public String toString() {
        return "Config{baseUrl='" + baseUrl + "', environment='" + environment
            + "', debug=" + debug + ", enabled=" + enabled + "}";
    }
}

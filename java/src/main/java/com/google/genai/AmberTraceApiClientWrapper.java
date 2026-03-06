package com.google.genai;

import com.google.genai.types.HttpOptions;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.lang.reflect.Field;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import java.util.function.BiConsumer;

/**
 * Tracing wrapper around Gemini's package-private {@link ApiClient}.
 *
 * <p>This class lives in {@code com.google.genai} to access package-private types.
 * It wraps an existing {@code ApiClient} and intercepts {@code generateContent} HTTP
 * requests to enable tracing.
 *
 * <p>Used internally by the AmberTrace SDK's Gemini interceptor.
 */
@SuppressWarnings({"unchecked", "rawtypes"})
public class AmberTraceApiClientWrapper extends ApiClient {

    private static final Logger logger = LoggerFactory.getLogger(AmberTraceApiClientWrapper.class);
    private final ApiClient delegate;
    private final BiConsumer<Map<String, Object>, Exception> traceCallback;

    /**
     * Create a tracing wrapper.
     *
     * @param delegate the original ApiClient to wrap
     * @param traceCallback called with (traceData, error) after each traced request
     */
    public AmberTraceApiClientWrapper(ApiClient delegate,
                                       BiConsumer<Map<String, Object>, Exception> traceCallback) {
        // Use the 2-arg protected constructor: (Optional<String> apiKey, Optional<HttpOptions>)
        super(delegate.apiKey, Optional.ofNullable(delegate.httpOptions));
        this.delegate = delegate;
        this.traceCallback = traceCallback;

        // Copy additional config from delegate so non-abstract methods work correctly.
        // vertexAI is final, so we use reflection to set it.
        this.httpClient = delegate.httpClient;
        this.httpOptions = delegate.httpOptions;
        try {
            Field vertexField = ApiClient.class.getDeclaredField("vertexAI");
            vertexField.setAccessible(true);
            vertexField.set(this, delegate.vertexAI);
        } catch (Exception ignored) {
            // Best-effort: vertexAI defaults to false
        }
    }

    @Override
    public ApiResponse request(String httpMethod, String path,
                                String requestJson, Optional<HttpOptions> httpOptions) {
        if (shouldTrace(path)) {
            return tracedRequest(httpMethod, path, requestJson, httpOptions);
        }
        return delegate.request(httpMethod, path, requestJson, httpOptions);
    }

    @Override
    public ApiResponse request(String httpMethod, String path,
                                byte[] requestBytes, Optional<HttpOptions> httpOptions) {
        return delegate.request(httpMethod, path, requestBytes, httpOptions);
    }

    // --- Static helpers for GeminiInterceptor ---

    /**
     * Extract the ApiClient from a Models instance.
     * Accessible because we're in the same package.
     */
    public static Object extractApiClient(Models models) {
        return models.apiClient;
    }

    /**
     * Create a tracing wrapper around the given ApiClient.
     * This method exists so callers outside this package don't need to
     * reference the package-private ApiClient type directly.
     *
     * @param originalApiClient the original ApiClient (as Object)
     * @param traceCallback called with (traceData, error) after each traced request
     * @return the wrapper (as Object)
     */
    public static Object wrapApiClient(Object originalApiClient,
                                        BiConsumer<Map<String, Object>, Exception> traceCallback) {
        return new AmberTraceApiClientWrapper((ApiClient) originalApiClient, traceCallback);
    }

    /**
     * Create a new Models with the given ApiClient wrapper.
     *
     * @param wrapper the wrapper (as Object, must be an AmberTraceApiClientWrapper)
     * @return new Models instance
     */
    public static Models createModels(Object wrapper) {
        return new Models((ApiClient) wrapper);
    }

    /**
     * Extract model name from API path.
     * e.g. "models/gemini-2.0-flash:generateContent" -> "gemini-2.0-flash"
     */
    public static String extractModel(String path) {
        if (path == null) return "unknown";
        int colonIdx = path.lastIndexOf(':');
        if (colonIdx < 0) return path;
        String modelPath = path.substring(0, colonIdx);
        int slashIdx = modelPath.lastIndexOf('/');
        return slashIdx >= 0 ? modelPath.substring(slashIdx + 1) : modelPath;
    }

    // --- Tracing logic ---

    private boolean shouldTrace(String path) {
        return path != null && path.contains("generateContent");
    }

    private ApiResponse tracedRequest(String httpMethod, String path,
                                       String requestJson, Optional<HttpOptions> httpOptions) {
        long startTime = System.nanoTime();
        String model = extractModel(path);

        try {
            ApiResponse response = delegate.request(httpMethod, path, requestJson, httpOptions);
            double durationMs = (System.nanoTime() - startTime) / 1_000_000.0;
            notifyTrace(model, requestJson, durationMs, null);
            return response;
        } catch (Exception e) {
            double durationMs = (System.nanoTime() - startTime) / 1_000_000.0;
            notifyTrace(model, requestJson, durationMs, e);
            throw e;
        }
    }

    private void notifyTrace(String model, String requestJson, double durationMs, Exception error) {
        try {
            Map<String, Object> traceData = new LinkedHashMap<>();
            traceData.put("model", model);
            traceData.put("requestJson", requestJson);
            traceData.put("durationMs", durationMs);
            traceCallback.accept(traceData, error);
        } catch (Exception e) {
            logger.debug("Error in trace callback: {}", e.getMessage());
        }
    }
}

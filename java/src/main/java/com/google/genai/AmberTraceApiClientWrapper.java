package com.google.genai;

import com.google.genai.types.ClientOptions;
import com.google.genai.types.HttpOptions;
import org.apache.http.HttpEntity;
import org.apache.http.entity.ByteArrayEntity;
import org.apache.http.util.EntityUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
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

    private AmberTraceApiClientWrapper(ApiClient delegate,
                                        BiConsumer<Map<String, Object>, Exception> traceCallback) {
        super(delegate.apiKey,
              Optional.ofNullable(delegate.httpOptions),
              delegate.clientOptions);
        this.delegate = delegate;
        this.traceCallback = traceCallback;
        copyDelegateFields(delegate);
    }

    private void copyDelegateFields(ApiClient delegate) {
        this.httpClient = delegate.httpClient;
        this.httpOptions = delegate.httpOptions;
        copyField(delegate, "vertexAI");
        copyField(delegate, "project");
        copyField(delegate, "location");
        copyField(delegate, "credentials");
    }

    private void copyField(ApiClient delegate, String fieldName) {
        try {
            Field f = ApiClient.class.getDeclaredField(fieldName);
            f.setAccessible(true);
            f.set(this, f.get(delegate));
        } catch (Exception ignored) {
            // Field may not exist in this version — safe to skip
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

    // --- Static helpers for GoogleInterceptor ---

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

            // Buffer the response body so both tracing and the SDK can read it
            String responseJson = bufferResponseBody(response);
            notifyTrace(model, requestJson, responseJson, durationMs, null);
            return response;
        } catch (Exception e) {
            double durationMs = (System.nanoTime() - startTime) / 1_000_000.0;
            notifyTrace(model, requestJson, null, durationMs, e);
            throw e;
        }
    }

    /**
     * Read the response entity body and replace it with a repeatable byte array entity
     * so the SDK can still consume it after we've read it for tracing.
     */
    private String bufferResponseBody(ApiResponse response) {
        try {
            HttpEntity entity = response.getEntity();
            if (entity == null) return null;

            byte[] bytes = EntityUtils.toByteArray(entity);
            String json = new String(bytes, StandardCharsets.UTF_8);

            // Replace the entity with a repeatable one via reflection on HttpApiResponse
            Field responseField = HttpApiResponse.class.getDeclaredField("response");
            responseField.setAccessible(true);
            Object httpResponse = responseField.get(response);
            if (httpResponse instanceof org.apache.http.HttpResponse) {
                ByteArrayEntity buffered = new ByteArrayEntity(bytes);
                buffered.setContentType(entity.getContentType());
                ((org.apache.http.HttpResponse) httpResponse).setEntity(buffered);
            }
            return json;
        } catch (Exception e) {
            logger.debug("Could not buffer response body for tracing: {}", e.getMessage());
            return null;
        }
    }

    private void notifyTrace(String model, String requestJson, String responseJson,
                             double durationMs, Exception error) {
        try {
            Map<String, Object> traceData = new LinkedHashMap<>();
            traceData.put("model", model);
            traceData.put("requestJson", requestJson);
            traceData.put("responseJson", responseJson);
            traceData.put("durationMs", durationMs);
            traceCallback.accept(traceData, error);
        } catch (Exception e) {
            logger.debug("Error in trace callback: {}", e.getMessage());
        }
    }
}

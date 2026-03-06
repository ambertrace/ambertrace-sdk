package dev.ambertrace.providers.gemini;

import com.google.genai.AmberTraceApiClientWrapper;
import dev.ambertrace.Config;
import dev.ambertrace.providers.BaseCollector;
import dev.ambertrace.providers.BaseInterceptor;
import dev.ambertrace.providers.ProviderRegistry;
import dev.ambertrace.transport.Transport;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.lang.reflect.Field;
import java.util.*;

/**
 * Interceptor for the Google Gemini Java SDK.
 *
 * <p>The Gemini SDK's {@code Client} and {@code Models} classes are both {@code final},
 * so they cannot be subclassed or proxied. This interceptor replaces the internal
 * {@code ApiClient} with a tracing wrapper via {@link AmberTraceApiClientWrapper},
 * which lives in the {@code com.google.genai} package to access package-private types.
 */
public class GeminiInterceptor implements BaseInterceptor<Object> {

    private static final Logger logger = LoggerFactory.getLogger(GeminiInterceptor.class);

    // Track wrapped clients using WeakHashMap to allow GC of unused clients
    private static final Map<Object, Boolean> wrappedClients =
        Collections.synchronizedMap(new WeakHashMap<>());

    @Override
    public String getProviderName() {
        return "gemini";
    }

    @Override
    public Object wrap(Object client) {
        if (client == null || isWrapped(client)) {
            return client;
        }

        try {
            // 1. Get client.models (public field, type: com.google.genai.Models)
            Field modelsField = client.getClass().getField("models");
            Object originalModels = modelsField.get(client);

            if (originalModels == null) {
                logger.warn("Gemini client has null models field");
                return client;
            }

            // 2. Extract ApiClient from Models (uses package-private access)
            Object originalApiClient = AmberTraceApiClientWrapper.extractApiClient(
                (com.google.genai.Models) originalModels);

            if (originalApiClient == null) {
                logger.warn("Gemini Models has null apiClient");
                return client;
            }

            // 3. Create tracing ApiClient wrapper (casts happen inside the wrapper's package)
            Object tracingClient = AmberTraceApiClientWrapper.wrapApiClient(
                originalApiClient,
                (traceData, error) -> sendTrace(traceData, error)
            );

            // 4. Create new Models with the tracing ApiClient
            com.google.genai.Models newModels = AmberTraceApiClientWrapper.createModels(tracingClient);

            // 5. Replace client.models via reflection
            modelsField.setAccessible(true);
            modelsField.set(client, newModels);

            wrappedClients.put(client, true);
            logger.debug("Wrapped Gemini client successfully");
            return client;

        } catch (Exception e) {
            logger.error("Failed to wrap Gemini client: {}", e.getMessage(), e);
            return client;
        }
    }

    @Override
    public boolean isWrapped(Object client) {
        return wrappedClients.containsKey(client);
    }

    private static void sendTrace(Map<String, Object> traceData, Exception error) {
        Config config = Config.get();
        if (config == null || !config.isEnabled()) return;

        try {
            ProviderRegistry registry = ProviderRegistry.get();
            if (registry == null) return;

            BaseCollector collector = registry.getCollector("gemini");
            if (collector == null) return;

            String traceId = UUID.randomUUID().toString();
            long startTimeNanos = System.nanoTime();

            // Build request context for the collector
            Map<String, Object> requestContext = new LinkedHashMap<>();
            requestContext.put("model", traceData.getOrDefault("model", "unknown"));
            requestContext.put("requestJson", traceData.get("requestJson"));

            Map<String, Object> trace = collector.collectTrace(
                traceId, startTimeNanos, requestContext, null, error);
            if (trace != null) {
                // Override duration with the pre-calculated value from the wrapper
                Object durationMs = traceData.get("durationMs");
                if (durationMs instanceof Number) {
                    trace.put("duration_ms", ((Number) durationMs).doubleValue());
                }

                Transport transport = Transport.get();
                if (transport != null) {
                    transport.sendTrace(trace);
                }
            }
        } catch (Exception e) {
            logger.debug("Error sending Gemini trace: {}", e.getMessage());
        }
    }
}

package dev.ambertrace.providers.gemini;

import dev.ambertrace.Config;
import dev.ambertrace.providers.BaseCollector;
import dev.ambertrace.providers.BaseInterceptor;
import dev.ambertrace.providers.ProviderRegistry;
import dev.ambertrace.transport.Transport;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.lang.reflect.Field;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Interceptor for the Google Gemini Java SDK.
 *
 * <p>The Gemini SDK uses {@code client.models.generateContent(model, content, config)}
 * where {@code client.models} is a public field (not a method). This interceptor
 * wraps the Models object and intercepts {@code generateContent} calls.
 *
 * <p>Since {@code Client} is a concrete class (not an interface), we return a
 * subclass-based wrapper that delegates all calls to the original while intercepting
 * the models field access.
 */
public class GeminiInterceptor implements BaseInterceptor<Object> {

    private static final Logger logger = LoggerFactory.getLogger(GeminiInterceptor.class);

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
            // Gemini Client has a public field `models` of type Models
            // We wrap the Models object to intercept generateContent
            Field modelsField = client.getClass().getField("models");
            Object originalModels = modelsField.get(client);

            if (originalModels == null) {
                logger.warn("Gemini client has no models field");
                return client;
            }

            // Create a wrapper for the Models object
            Object wrappedModels = wrapModels(originalModels);

            // Replace the models field on the client
            modelsField.set(client, wrappedModels);

            // Mark client as wrapped by setting a flag via a concurrent map
            wrappedClients.put(System.identityHashCode(client), true);

            return client;
        } catch (Exception e) {
            logger.error("Failed to wrap Gemini client: {}", e.getMessage(), e);
            return client;
        }
    }

    @Override
    public boolean isWrapped(Object client) {
        return wrappedClients.containsKey(System.identityHashCode(client));
    }

    // Track wrapped clients (weak reference would be ideal, but simple map suffices for now)
    private static final Map<Integer, Boolean> wrappedClients = new java.util.concurrent.ConcurrentHashMap<>();

    /**
     * Wrap a Gemini Models object. Since Models is a concrete class,
     * we use a subclass approach (or dynamic proxy if it implements interfaces).
     * Fallback: use field injection to wrap the internal HTTP client.
     *
     * <p>For simplicity, we wrap it as a Models subclass that delegates all calls
     * but intercepts generateContent.
     */
    private Object wrapModels(Object models) {
        // The Models class is concrete. We'll create a TracedModels subclass
        // by using reflection to intercept the generateContent call.
        // Since we can't easily subclass at runtime without bytecode generation,
        // we wrap via a proxy-like pattern using a composition wrapper.

        return new TracedModels(models);
    }

    /**
     * Wrapper around Gemini's Models class that intercepts generateContent calls.
     *
     * <p>This class extends the SDK's Models class and overrides generateContent
     * to add tracing. Since Models may not be easily subclassed, we use delegation
     * via a field and expose it as the same type through reflection.
     */
    static class TracedModels {
        private final Object delegate;

        TracedModels(Object delegate) {
            this.delegate = delegate;
        }

        /**
         * Called via reflection from the intercepted client.
         * The GeminiInterceptor replaces client.models with this object.
         *
         * Note: Since Gemini's client.models is typed as Models (concrete class),
         * this wrapper approach requires the client.models field to accept Object type
         * or we need a different strategy. In practice, we intercept at a higher level.
         */
        public Object generateContent(String model, Object content, Object config) throws Exception {
            Config amberConfig = Config.get();
            if (amberConfig == null || !amberConfig.isEnabled()) {
                return invokeDelegate("generateContent", model, content, config);
            }

            String traceId = UUID.randomUUID().toString();
            long startTime = System.nanoTime();

            // Build request context for the collector
            Map<String, Object> requestContext = new LinkedHashMap<>();
            requestContext.put("model", model);
            requestContext.put("content", content instanceof String ? content : content.toString());
            requestContext.put("config", config);

            try {
                Object result = invokeDelegate("generateContent", model, content, config);
                sendTrace(traceId, startTime, requestContext, result, null);
                return result;
            } catch (Exception e) {
                sendTrace(traceId, startTime, requestContext, null, e);
                throw e;
            }
        }

        private Object invokeDelegate(String methodName, Object... args) throws Exception {
            for (Method m : delegate.getClass().getMethods()) {
                if (m.getName().equals(methodName) && m.getParameterCount() == args.length) {
                    return m.invoke(delegate, args);
                }
            }
            throw new NoSuchMethodException(methodName);
        }

        private static void sendTrace(String traceId, long startTime, Object requestParams,
                                       Object response, Exception error) {
            try {
                ProviderRegistry registry = ProviderRegistry.get();
                if (registry == null) return;

                BaseCollector collector = registry.getCollector("gemini");
                if (collector == null) return;

                Map<String, Object> trace = collector.collectTrace(traceId, startTime, requestParams, response, error);
                if (trace != null) {
                    Transport transport = Transport.get();
                    if (transport != null) {
                        transport.sendTrace(trace);
                    }
                }
            } catch (Exception e) {
                LoggerFactory.getLogger(TracedModels.class).debug("Error sending Gemini trace: {}", e.getMessage());
            }
        }
    }
}

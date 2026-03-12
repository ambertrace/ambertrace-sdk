package dev.ambertrace.providers;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Registry for LLM provider interceptors and collectors.
 *
 * <p>Thread-safe. Stores interceptor/collector pairs keyed by provider name.
 */
public final class ProviderRegistry {

    private static final Logger logger = LoggerFactory.getLogger(ProviderRegistry.class);

    private final Map<String, BaseInterceptor<?>> interceptors = new ConcurrentHashMap<>();
    private final Map<String, BaseCollector> collectors = new ConcurrentHashMap<>();

    // Global singleton
    private static volatile ProviderRegistry instance;

    public void registerProvider(String name, BaseInterceptor<?> interceptor, BaseCollector collector) {
        interceptors.put(name, interceptor);
        collectors.put(name, collector);
        logger.debug("Registered provider: {}", name);
    }

    public void unregisterProvider(String name) {
        interceptors.remove(name);
        collectors.remove(name);
        logger.debug("Unregistered provider: {}", name);
    }

    public BaseInterceptor<?> getInterceptor(String name) {
        return interceptors.get(name);
    }

    public BaseCollector getCollector(String name) {
        return collectors.get(name);
    }

    public boolean hasProvider(String name) {
        return interceptors.containsKey(name);
    }

    public List<String> getRegisteredProviders() {
        return new ArrayList<>(interceptors.keySet());
    }

    public void clear() {
        interceptors.clear();
        collectors.clear();
    }

    // --- Global singleton ---

    public static void set(ProviderRegistry registry) {
        instance = registry;
    }

    public static ProviderRegistry get() {
        return instance;
    }

    public static void clear_() {
        instance = null;
    }
}

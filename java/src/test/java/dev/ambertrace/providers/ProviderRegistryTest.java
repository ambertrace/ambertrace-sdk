package dev.ambertrace.providers;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class ProviderRegistryTest {

    @AfterEach
    void cleanup() {
        ProviderRegistry.clear_();
    }

    @Test
    void testRegisterAndRetrieve() {
        ProviderRegistry registry = new ProviderRegistry();

        MockInterceptor interceptor = new MockInterceptor("test-provider");
        MockCollector collector = new MockCollector("test-provider");

        registry.registerProvider("test-provider", interceptor, collector);

        assertTrue(registry.hasProvider("test-provider"));
        assertSame(interceptor, registry.getInterceptor("test-provider"));
        assertSame(collector, registry.getCollector("test-provider"));
        assertTrue(registry.getRegisteredProviders().contains("test-provider"));
    }

    @Test
    void testUnregister() {
        ProviderRegistry registry = new ProviderRegistry();

        registry.registerProvider("test", new MockInterceptor("test"), new MockCollector("test"));
        assertTrue(registry.hasProvider("test"));

        registry.unregisterProvider("test");
        assertFalse(registry.hasProvider("test"));
        assertNull(registry.getInterceptor("test"));
        assertNull(registry.getCollector("test"));
    }

    @Test
    void testClear() {
        ProviderRegistry registry = new ProviderRegistry();

        registry.registerProvider("a", new MockInterceptor("a"), new MockCollector("a"));
        registry.registerProvider("b", new MockInterceptor("b"), new MockCollector("b"));

        assertEquals(2, registry.getRegisteredProviders().size());

        registry.clear();
        assertTrue(registry.getRegisteredProviders().isEmpty());
    }

    @Test
    void testGlobalSingleton() {
        ProviderRegistry registry = new ProviderRegistry();
        ProviderRegistry.set(registry);

        assertSame(registry, ProviderRegistry.get());

        ProviderRegistry.clear_();
        assertNull(ProviderRegistry.get());
    }

    // --- Mock implementations ---

    static class MockInterceptor implements BaseInterceptor<Object> {
        private final String name;

        MockInterceptor(String name) {
            this.name = name;
        }

        @Override
        public Object wrap(Object client) { return client; }

        @Override
        public boolean isWrapped(Object client) { return false; }

        @Override
        public String getProviderName() { return name; }
    }

    static class MockCollector extends BaseCollector {
        private final String name;

        MockCollector(String name) {
            this.name = name;
        }

        @Override
        public Map<String, Object> collectTrace(String traceId, long startTimeNanos,
                                                  Object requestParams, Object response, Exception error) {
            return null;
        }

        @Override
        public String getProviderName() { return name; }
    }
}

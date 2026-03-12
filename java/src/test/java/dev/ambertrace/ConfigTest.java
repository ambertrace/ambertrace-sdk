package dev.ambertrace;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class ConfigTest {

    @AfterEach
    void cleanup() {
        Config.clear();
    }

    @Test
    void testBuilderWithExplicitValues() {
        Config config = Config.builder()
            .apiKey("at_test123")
            .baseUrl("https://custom.api.dev")
            .environment("staging")
            .debug(true)
            .timeoutMs(10000)
            .enabled(true)
            .build();

        assertEquals("at_test123", config.getApiKey());
        assertEquals("https://custom.api.dev", config.getBaseUrl());
        assertEquals("staging", config.getEnvironment());
        assertTrue(config.isDebug());
        assertEquals(10000, config.getTimeoutMs());
        assertTrue(config.isEnabled());
    }

    @Test
    void testDefaultValues() {
        Config config = Config.builder()
            .apiKey("at_test123")
            .build();

        assertEquals("https://api.ambertrace.dev", config.getBaseUrl());
        assertNull(config.getEnvironment());
        assertFalse(config.isDebug());
        assertEquals(5000, config.getTimeoutMs());
        assertTrue(config.isEnabled());
    }

    @Test
    void testTracesEndpoint() {
        Config config = Config.builder()
            .apiKey("at_test123")
            .baseUrl("https://custom.api.dev")
            .build();

        assertEquals("https://custom.api.dev/api/traces/ingest", config.getTracesEndpoint());
    }

    @Test
    void testAuthHeader() {
        Config config = Config.builder()
            .apiKey("at_test123")
            .build();

        assertEquals("Bearer at_test123", config.getAuthHeader());
    }

    @Test
    void testMissingApiKeyThrows() {
        assertThrows(IllegalArgumentException.class, () ->
            Config.builder().build()
        );
    }

    @Test
    void testGlobalSingleton() {
        Config config = Config.builder().apiKey("at_test").build();
        Config.set(config);

        assertSame(config, Config.get());

        Config.clear();
        assertNull(Config.get());
    }

    @Test
    void testDisabledConfig() {
        Config config = Config.builder()
            .apiKey("at_test123")
            .enabled(false)
            .build();

        assertFalse(config.isEnabled());
    }
}

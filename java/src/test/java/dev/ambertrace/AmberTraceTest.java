package dev.ambertrace;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class AmberTraceTest {

    @AfterEach
    void cleanup() {
        AmberTrace.shutdown();
    }

    @Test
    void testInitWithApiKey() {
        AmberTrace.init("at_test_key_123");

        assertTrue(AmberTrace.isEnabled());
        assertEquals("0.1.0", AmberTrace.getVersion());
    }

    @Test
    void testInitWithConfig() {
        Config config = Config.builder()
            .apiKey("at_test_key")
            .environment("test")
            .debug(true)
            .build();

        AmberTrace.init(config);
        assertTrue(AmberTrace.isEnabled());
    }

    @Test
    void testInitDisabled() {
        Config config = Config.builder()
            .apiKey("at_test_key")
            .enabled(false)
            .build();

        AmberTrace.init(config);
        assertFalse(AmberTrace.isEnabled());
    }

    @Test
    void testEnableDisable() {
        AmberTrace.init("at_test_key");
        assertTrue(AmberTrace.isEnabled());

        AmberTrace.disable();
        assertFalse(AmberTrace.isEnabled());

        AmberTrace.enable();
        assertTrue(AmberTrace.isEnabled());
    }

    @Test
    void testShutdown() {
        AmberTrace.init("at_test_key");
        assertTrue(AmberTrace.isEnabled());

        AmberTrace.shutdown();
        assertFalse(AmberTrace.isEnabled());
    }

    @Test
    void testWrapNullReturnsNull() {
        AmberTrace.init("at_test_key");
        assertNull(AmberTrace.wrap(null));
    }

    @Test
    void testWrapUnknownTypeReturnsOriginal() {
        AmberTrace.init("at_test_key");
        String original = "not a client";
        assertSame(original, AmberTrace.wrap(original));
    }

    @Test
    void testWrapWithoutInitReturnsOriginal() {
        // Don't call init
        Object original = new Object();
        assertSame(original, AmberTrace.wrap(original));
    }

    @Test
    void testFlushWithoutInit() {
        // Should not throw
        AmberTrace.flush();
    }

    @Test
    void testVersion() {
        assertEquals("0.1.0", AmberTrace.getVersion());
    }
}

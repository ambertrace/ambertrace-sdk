package dev.ambertrace;

import dev.ambertrace.providers.BaseInterceptor;
import dev.ambertrace.providers.ProviderRegistry;
import dev.ambertrace.transport.Transport;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Main entry point for the AmberTrace Java SDK.
 *
 * <p>Usage:
 * <pre>{@code
 * // Initialize
 * AmberTrace.init("at_your_api_key");
 *
 * // Wrap your LLM client
 * OpenAIClient client = AmberTrace.wrap(originalClient);
 *
 * // Use the client normally — calls are traced automatically
 * ChatCompletion completion = client.chat().completions().create(params);
 *
 * // Flush before exit
 * AmberTrace.flush();
 * }</pre>
 *
 * <p>Supported providers (auto-detected):
 * <ul>
 *   <li>OpenAI (com.openai:openai-java)</li>
 *   <li>Anthropic (com.anthropic:anthropic-java)</li>
 *   <li>Google Gemini (com.google.genai:google-genai)</li>
 * </ul>
 */
public final class AmberTrace {

    private static final Logger logger = LoggerFactory.getLogger(AmberTrace.class);

    // Track the shutdown hook to prevent accumulation on repeated init() calls
    private static volatile Thread shutdownHook;

    private AmberTrace() {}

    /**
     * Initialize with an API key. All other settings use defaults or env vars.
     *
     * @param apiKey AmberTrace API key
     */
    public static void init(String apiKey) {
        init(Config.builder().apiKey(apiKey).build());
    }

    /**
     * Initialize from environment variables only (AMBERTRACE_API_KEY, etc.).
     *
     * <p>If no API key is found in environment variables, logs a warning
     * and disables tracing instead of throwing.
     */
    public static void init() {
        try {
            init(Config.builder().build());
        } catch (IllegalArgumentException e) {
            logger.warn("AmberTrace API key not found: {}. Tracing will be disabled.", e.getMessage());
        }
    }

    /**
     * Initialize with full configuration.
     *
     * @param config SDK configuration
     */
    public static void init(Config config) {
        try {
            Config.set(config);
            logger.debug("Initialized with config: {}", config);

            if (!config.isEnabled()) {
                logger.info("AmberTrace initialized but disabled (enabled=false)");
                return;
            }

            // Create provider registry
            ProviderRegistry registry = new ProviderRegistry();

            // Auto-detect and register providers
            detectAndRegisterProviders(registry);

            if (registry.getRegisteredProviders().isEmpty()) {
                logger.warn(
                    "No supported LLM SDKs found. Install 'com.openai:openai-java', "
                    + "'com.anthropic:anthropic-java', or 'com.google.genai:google-genai' "
                    + "to enable tracing."
                );
                return;
            }

            // Create and start transport
            Transport transport = new Transport();
            transport.start();
            Transport.set(transport);

            // Store registry
            ProviderRegistry.set(registry);

            // Remove previous shutdown hook if exists, then register new one
            if (shutdownHook != null) {
                try {
                    Runtime.getRuntime().removeShutdownHook(shutdownHook);
                } catch (IllegalStateException ignored) {
                    // JVM is already shutting down
                }
            }
            shutdownHook = new Thread(() -> {
                try {
                    flush(5000);
                    Transport t = Transport.get();
                    if (t != null) t.stop();
                } catch (Exception ignored) {}
            }, "ambertrace-shutdown");
            Runtime.getRuntime().addShutdownHook(shutdownHook);

            logger.info("AmberTrace SDK initialized for providers: {}", registry.getRegisteredProviders());

        } catch (Exception e) {
            logger.error("Failed to initialize AmberTrace: {}", e.getMessage(), e);
            logger.warn("AmberTrace initialization failed, tracing will be disabled");
        }
    }

    /**
     * Wrap an LLM provider client to enable tracing.
     *
     * <p>Returns a traced proxy that records timing and delegates to the original.
     * If tracing is not initialized or disabled, returns the original client unchanged.
     *
     * @param client the provider SDK client (OpenAIClient, AnthropicClient, or Gemini Client)
     * @param <T> the client type
     * @return traced wrapper with the same API, or the original if wrapping fails
     */
    @SuppressWarnings("unchecked")
    public static <T> T wrap(T client) {
        if (client == null) {
            return null;
        }

        Config config = Config.get();
        if (config == null || !config.isEnabled()) {
            return client;
        }

        ProviderRegistry registry = ProviderRegistry.get();
        if (registry == null) {
            logger.warn("AmberTrace not initialized, call init() first");
            return client;
        }

        // Find matching interceptor by checking instanceof
        String providerName = detectProvider(client);
        if (providerName == null) {
            logger.warn("Unknown client type: {}. Supported: OpenAI, Anthropic, Gemini", client.getClass().getName());
            return client;
        }

        BaseInterceptor<?> interceptor = registry.getInterceptor(providerName);
        if (interceptor == null) {
            logger.warn("No interceptor registered for provider: {}", providerName);
            return client;
        }

        try {
            return (T) ((BaseInterceptor<Object>) interceptor).wrap(client);
        } catch (Exception e) {
            logger.error("Failed to wrap {} client: {}", providerName, e.getMessage(), e);
            return client;
        }
    }

    /**
     * Block until all pending traces are sent.
     *
     * @param timeoutMs maximum time to wait in milliseconds
     */
    public static void flush(long timeoutMs) {
        try {
            Transport transport = Transport.get();
            if (transport != null) {
                transport.flush(timeoutMs);
                logger.debug("Flush completed");
            }
        } catch (Exception e) {
            logger.error("Failed to flush traces: {}", e.getMessage(), e);
        }
    }

    /** Block until all pending traces are sent (default 5s timeout). */
    public static void flush() {
        flush(5000);
    }

    /** Disable tracing. Wrapped clients continue to work but traces are not collected. */
    public static void disable() {
        try {
            Config config = Config.get();
            if (config != null) {
                // Replace with disabled config
                Config.set(Config.builder()
                    .apiKey(config.getApiKey())
                    .baseUrl(config.getBaseUrl())
                    .environment(config.getEnvironment())
                    .debug(config.isDebug())
                    .timeoutMs(config.getTimeoutMs())
                    .enabled(false)
                    .build());
            }
            logger.info("AmberTrace tracing disabled");
        } catch (Exception e) {
            logger.error("Failed to disable AmberTrace: {}", e.getMessage(), e);
        }
    }

    /** Re-enable tracing after calling {@link #disable()}. */
    public static void enable() {
        try {
            Config config = Config.get();
            if (config != null) {
                Config.set(Config.builder()
                    .apiKey(config.getApiKey())
                    .baseUrl(config.getBaseUrl())
                    .environment(config.getEnvironment())
                    .debug(config.isDebug())
                    .timeoutMs(config.getTimeoutMs())
                    .enabled(true)
                    .build());
            }
            logger.info("AmberTrace tracing enabled");
        } catch (Exception e) {
            logger.error("Failed to enable AmberTrace: {}", e.getMessage(), e);
        }
    }

    /** Check if tracing is currently enabled. */
    public static boolean isEnabled() {
        Config config = Config.get();
        return config != null && config.isEnabled();
    }

    /** Shut down the SDK: flush pending traces, stop transport, clear state. */
    public static void shutdown() {
        try {
            flush(5000);
            Transport.clear();
            ProviderRegistry.clear_();
            Config.clear();
            logger.info("AmberTrace shut down");
        } catch (Exception e) {
            logger.error("Failed to shut down AmberTrace: {}", e.getMessage(), e);
        }
    }

    /** Get the SDK version string. */
    public static String getVersion() {
        return Version.VERSION;
    }

    // --- Internal ---

    private static void detectAndRegisterProviders(ProviderRegistry registry) {
        // OpenAI
        if (isClassAvailable("com.openai.client.OpenAIClient")) {
            try {
                var interceptor = new dev.ambertrace.providers.openai.OpenAIInterceptor();
                var collector = new dev.ambertrace.providers.openai.OpenAICollector();
                registry.registerProvider("openai", interceptor, collector);
                logger.debug("Registered OpenAI provider");
            } catch (Exception e) {
                logger.debug("Failed to register OpenAI provider: {}", e.getMessage());
            }
        } else {
            logger.info("OpenAI SDK not found, skipping OpenAI tracing");
        }

        // Anthropic
        if (isClassAvailable("com.anthropic.client.AnthropicClient")) {
            try {
                var interceptor = new dev.ambertrace.providers.anthropic.AnthropicInterceptor();
                var collector = new dev.ambertrace.providers.anthropic.AnthropicCollector();
                registry.registerProvider("anthropic", interceptor, collector);
                logger.debug("Registered Anthropic provider");
            } catch (Exception e) {
                logger.debug("Failed to register Anthropic provider: {}", e.getMessage());
            }
        } else {
            logger.info("Anthropic SDK not found, skipping Anthropic tracing");
        }

        // Google Gemini
        if (isClassAvailable("com.google.genai.Client")) {
            try {
                var interceptor = new dev.ambertrace.providers.google.GoogleInterceptor();
                var collector = new dev.ambertrace.providers.google.GoogleCollector();
                registry.registerProvider("gemini", interceptor, collector);
                logger.debug("Registered Gemini provider");
            } catch (Exception e) {
                logger.debug("Failed to register Gemini provider: {}", e.getMessage());
            }
        } else {
            logger.info("Gemini SDK not found, skipping Gemini tracing");
        }
    }

    private static String detectProvider(Object client) {
        String className = client.getClass().getName();

        // Check interfaces (including on proxy classes)
        Class<?> cls = client.getClass();
        while (cls != null) {
            for (Class<?> iface : cls.getInterfaces()) {
                String ifaceName = iface.getName();
                if (ifaceName.startsWith("com.openai.")) return "openai";
                if (ifaceName.startsWith("com.anthropic.")) return "anthropic";
            }
            cls = cls.getSuperclass();
        }

        // Check class name directly
        if (className.startsWith("com.openai.")) return "openai";
        if (className.startsWith("com.anthropic.")) return "anthropic";
        if (className.startsWith("com.google.genai.")) return "gemini";

        return null;
    }

    private static boolean isClassAvailable(String className) {
        try {
            Class.forName(className);
            return true;
        } catch (ClassNotFoundException e) {
            return false;
        }
    }
}

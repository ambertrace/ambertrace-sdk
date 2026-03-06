package dev.ambertrace.providers;

/**
 * Interface for provider-specific interceptors.
 *
 * <p>Java uses the wrapper/decorator pattern instead of monkey-patching.
 * {@link #wrap(Object)} returns a traced proxy that records timing and
 * delegates to the original client.
 *
 * @param <T> the provider client type (e.g., OpenAIClient)
 */
public interface BaseInterceptor<T> {

    /**
     * Wrap a provider client to enable tracing.
     *
     * @param client the original provider SDK client
     * @return a traced wrapper with the same API, or the original client if wrapping fails
     */
    T wrap(T client);

    /**
     * Check if a given client is already a traced wrapper.
     *
     * @param client the client to check
     * @return true if the client is already wrapped
     */
    boolean isWrapped(T client);

    /** Return the provider name (e.g., "openai", "anthropic", "gemini"). */
    String getProviderName();
}

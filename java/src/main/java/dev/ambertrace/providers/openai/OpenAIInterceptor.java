package dev.ambertrace.providers.openai;

import dev.ambertrace.Config;
import dev.ambertrace.providers.BaseCollector;
import dev.ambertrace.providers.BaseInterceptor;
import dev.ambertrace.providers.ProviderRegistry;
import dev.ambertrace.transport.Transport;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

/**
 * Interceptor for the OpenAI Java SDK.
 *
 * <p>Wraps {@code OpenAIClient} using a JDK dynamic proxy. The proxy intercepts
 * calls to {@code chat()} to return a traced chain:
 * {@code client.chat().completions().create(params)} → traced.
 */
public class OpenAIInterceptor implements BaseInterceptor<Object> {

    private static final Logger logger = LoggerFactory.getLogger(OpenAIInterceptor.class);
    private static final String MARKER_METHOD = "__ambertraceWrapped";

    @Override
    public String getProviderName() {
        return "openai";
    }

    @Override
    @SuppressWarnings("unchecked")
    public Object wrap(Object client) {
        if (client == null || isWrapped(client)) {
            return client;
        }

        try {
            Class<?> clientInterface = findInterface(client, "com.openai.client.OpenAIClient");
            if (clientInterface == null) {
                logger.warn("Could not find OpenAIClient interface on {}", client.getClass().getName());
                return client;
            }

            return Proxy.newProxyInstance(
                client.getClass().getClassLoader(),
                new Class<?>[]{ clientInterface },
                new OpenAIClientHandler(client)
            );
        } catch (Exception e) {
            logger.error("Failed to wrap OpenAI client: {}", e.getMessage(), e);
            return client;
        }
    }

    @Override
    public boolean isWrapped(Object client) {
        return Proxy.isProxyClass(client.getClass())
            && Proxy.getInvocationHandler(client) instanceof OpenAIClientHandler;
    }

    // --- Handler for OpenAIClient proxy ---

    private static class OpenAIClientHandler implements InvocationHandler {
        private final Object delegate;

        OpenAIClientHandler(Object delegate) {
            this.delegate = delegate;
        }

        @Override
        public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
            // Intercept chat() to return a traced Chat proxy
            if ("chat".equals(method.getName()) && (args == null || args.length == 0)) {
                Object chat = method.invoke(delegate, args);
                return wrapChat(chat);
            }
            return method.invoke(delegate, args);
        }
    }

    // --- Wrap Chat resource ---

    private static Object wrapChat(Object chat) {
        Class<?> chatInterface = findInterface(chat, "Chat");
        if (chatInterface == null) {
            return chat;
        }
        return Proxy.newProxyInstance(
            chat.getClass().getClassLoader(),
            new Class<?>[]{ chatInterface },
            (proxy, method, args) -> {
                if ("completions".equals(method.getName())) {
                    Object completions = method.invoke(chat, args);
                    return wrapCompletions(completions);
                }
                return method.invoke(chat, args);
            }
        );
    }

    // --- Wrap Completions resource ---

    private static Object wrapCompletions(Object completions) {
        Class<?> completionsInterface = findInterface(completions, "Completions");
        if (completionsInterface == null) {
            return completions;
        }
        return Proxy.newProxyInstance(
            completions.getClass().getClassLoader(),
            new Class<?>[]{ completionsInterface },
            (proxy, method, args) -> {
                if ("create".equals(method.getName()) && args != null && args.length == 1) {
                    return interceptCreate(completions, method, args);
                }
                return method.invoke(completions, args);
            }
        );
    }

    // --- Core interception logic ---

    private static Object interceptCreate(Object completions, Method method, Object[] args) throws Throwable {
        Config config = Config.get();
        if (config == null || !config.isEnabled()) {
            return method.invoke(completions, args);
        }

        String traceId = UUID.randomUUID().toString();
        long startTime = System.nanoTime();
        Object requestParams = args[0];

        try {
            Object result = method.invoke(completions, args);

            // Handle CompletableFuture (async client)
            if (result instanceof CompletableFuture) {
                CompletableFuture<?> future = (CompletableFuture<?>) result;
                final long st = startTime;
                return future.whenComplete((response, throwable) -> {
                    if (throwable != null) {
                        sendTrace(traceId, st, requestParams, null,
                            throwable instanceof Exception ? (Exception) throwable : new RuntimeException(throwable));
                    } else {
                        sendTrace(traceId, st, requestParams, response, null);
                    }
                });
            }

            // Sync response
            sendTrace(traceId, startTime, requestParams, result, null);
            return result;

        } catch (java.lang.reflect.InvocationTargetException e) {
            Throwable cause = e.getCause();
            sendTrace(traceId, startTime, requestParams, null,
                cause instanceof Exception ? (Exception) cause : new RuntimeException(cause));
            throw cause;
        } catch (Exception e) {
            sendTrace(traceId, startTime, requestParams, null, e);
            throw e;
        }
    }

    private static void sendTrace(String traceId, long startTime, Object requestParams,
                                   Object response, Exception error) {
        try {
            ProviderRegistry registry = ProviderRegistry.get();
            if (registry == null) return;

            BaseCollector collector = registry.getCollector("openai");
            if (collector == null) return;

            Map<String, Object> trace = collector.collectTrace(traceId, startTime, requestParams, response, error);
            if (trace != null) {
                Transport transport = Transport.get();
                if (transport != null) {
                    transport.sendTrace(trace);
                }
            }
        } catch (Exception e) {
            logger.debug("Error sending OpenAI trace: {}", e.getMessage());
        }
    }

    // --- Utility ---

    private static Class<?> findInterface(Object obj, String nameContains) {
        for (Class<?> iface : obj.getClass().getInterfaces()) {
            if (iface.getName().contains(nameContains)) {
                return iface;
            }
        }
        // Check superclass interfaces
        Class<?> cls = obj.getClass().getSuperclass();
        while (cls != null) {
            for (Class<?> iface : cls.getInterfaces()) {
                if (iface.getName().contains(nameContains)) {
                    return iface;
                }
            }
            cls = cls.getSuperclass();
        }
        return null;
    }
}

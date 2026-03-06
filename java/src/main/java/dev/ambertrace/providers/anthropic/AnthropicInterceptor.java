package dev.ambertrace.providers.anthropic;

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
 * Interceptor for the Anthropic Java SDK.
 *
 * <p>Wraps {@code AnthropicClient} using a JDK dynamic proxy. Intercepts
 * {@code client.messages().create(params)} calls.
 */
public class AnthropicInterceptor implements BaseInterceptor<Object> {

    private static final Logger logger = LoggerFactory.getLogger(AnthropicInterceptor.class);

    @Override
    public String getProviderName() {
        return "anthropic";
    }

    @Override
    public Object wrap(Object client) {
        if (client == null || isWrapped(client)) {
            return client;
        }

        try {
            Class<?> clientInterface = findInterface(client, "com.anthropic.client.AnthropicClient");
            if (clientInterface == null) {
                logger.warn("Could not find AnthropicClient interface on {}", client.getClass().getName());
                return client;
            }

            return Proxy.newProxyInstance(
                client.getClass().getClassLoader(),
                new Class<?>[]{ clientInterface },
                new AnthropicClientHandler(client)
            );
        } catch (Exception e) {
            logger.error("Failed to wrap Anthropic client: {}", e.getMessage(), e);
            return client;
        }
    }

    @Override
    public boolean isWrapped(Object client) {
        return Proxy.isProxyClass(client.getClass())
            && Proxy.getInvocationHandler(client) instanceof AnthropicClientHandler;
    }

    private static class AnthropicClientHandler implements InvocationHandler {
        private final Object delegate;

        AnthropicClientHandler(Object delegate) {
            this.delegate = delegate;
        }

        @Override
        public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
            if ("messages".equals(method.getName()) && (args == null || args.length == 0)) {
                Object messages = method.invoke(delegate, args);
                return wrapMessages(messages);
            }
            return method.invoke(delegate, args);
        }
    }

    private static Object wrapMessages(Object messages) {
        Class<?> messagesInterface = findInterface(messages, "Messages");
        if (messagesInterface == null) {
            return messages;
        }
        return Proxy.newProxyInstance(
            messages.getClass().getClassLoader(),
            new Class<?>[]{ messagesInterface },
            (proxy, method, args) -> {
                if ("create".equals(method.getName()) && args != null && args.length == 1) {
                    return interceptCreate(messages, method, args);
                }
                return method.invoke(messages, args);
            }
        );
    }

    private static Object interceptCreate(Object messages, Method method, Object[] args) throws Throwable {
        Config config = Config.get();
        if (config == null || !config.isEnabled()) {
            return method.invoke(messages, args);
        }

        String traceId = UUID.randomUUID().toString();
        long startTime = System.nanoTime();
        Object requestParams = args[0];

        try {
            Object result = method.invoke(messages, args);

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

            BaseCollector collector = registry.getCollector("anthropic");
            if (collector == null) return;

            Map<String, Object> trace = collector.collectTrace(traceId, startTime, requestParams, response, error);
            if (trace != null) {
                Transport transport = Transport.get();
                if (transport != null) {
                    transport.sendTrace(trace);
                }
            }
        } catch (Exception e) {
            logger.debug("Error sending Anthropic trace: {}", e.getMessage());
        }
    }

    private static Class<?> findInterface(Object obj, String nameContains) {
        for (Class<?> iface : obj.getClass().getInterfaces()) {
            if (iface.getName().contains(nameContains)) {
                return iface;
            }
        }
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

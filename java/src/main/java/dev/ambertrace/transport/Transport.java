package dev.ambertrace.transport;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.ambertrace.Config;
import dev.ambertrace.Version;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Async HTTP transport for sending traces to the AmberTrace backend.
 *
 * <p>Uses a bounded thread pool with daemon threads. Traces are submitted
 * non-blocking; if the queue is full, new traces are silently dropped.
 * Errors are logged but never thrown to the caller.
 */
public final class Transport {

    private static final Logger logger = LoggerFactory.getLogger(Transport.class);
    private static final int MAX_QUEUE_SIZE = 1000;
    private static final int THREAD_POOL_SIZE = 2;

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final HttpClient httpClient;
    private final Semaphore queueBound = new Semaphore(MAX_QUEUE_SIZE);
    private final AtomicInteger droppedCount = new AtomicInteger(0);
    private final AtomicBoolean running = new AtomicBoolean(false);

    private ExecutorService executor;

    // Global singleton
    private static volatile Transport instance;

    public Transport() {
        this.httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofMillis(
                Config.get() != null ? Config.get().getTimeoutMs() : 5000
            ))
            .build();
    }

    /** Start the transport worker threads. Idempotent. */
    public synchronized void start() {
        if (running.get()) {
            return;
        }
        ThreadFactory factory = r -> {
            Thread t = new Thread(r, "ambertrace-transport");
            t.setDaemon(true);
            return t;
        };
        executor = new ThreadPoolExecutor(
            THREAD_POOL_SIZE, THREAD_POOL_SIZE,
            0L, TimeUnit.MILLISECONDS,
            new LinkedBlockingQueue<>(MAX_QUEUE_SIZE),
            factory,
            new ThreadPoolExecutor.DiscardPolicy()
        );
        running.set(true);
        logger.debug("Transport started");
    }

    /** Stop the transport and drain pending traces. */
    public synchronized void stop() {
        if (!running.get()) {
            return;
        }
        running.set(false);
        if (executor != null) {
            executor.shutdown();
            try {
                executor.awaitTermination(5, TimeUnit.SECONDS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                executor.shutdownNow();
            }
        }
        logger.debug("Transport stopped");
    }

    /**
     * Submit a trace for async delivery. Non-blocking, never throws.
     *
     * @param traceData serialized trace map (from {@code Trace.toMap()})
     */
    public void sendTrace(Map<String, Object> traceData) {
        if (!running.get() || executor == null) {
            logger.debug("Transport not running, dropping trace");
            return;
        }

        if (!queueBound.tryAcquire()) {
            int dropped = droppedCount.incrementAndGet();
            if (dropped % 100 == 1) {
                logger.warn("Trace queue full, {} traces dropped so far", dropped);
            }
            return;
        }

        try {
            executor.submit(() -> {
                try {
                    doSend(traceData);
                } finally {
                    queueBound.release();
                }
            });
        } catch (RejectedExecutionException e) {
            queueBound.release();
            logger.debug("Trace submission rejected (transport shutting down)");
        }
    }

    /** Block until all pending traces are sent or timeout is reached. */
    public void flush(long timeoutMs) {
        if (executor == null || !running.get()) {
            return;
        }
        try {
            // Submit a barrier task and wait for it to complete
            Future<?> barrier = executor.submit(() -> {});
            barrier.get(timeoutMs, TimeUnit.MILLISECONDS);
        } catch (TimeoutException e) {
            logger.warn("Flush timed out after {}ms", timeoutMs);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } catch (Exception e) {
            logger.debug("Flush error: {}", e.getMessage());
        }
    }

    public int getDroppedCount() {
        return droppedCount.get();
    }

    // --- Internal ---

    private void doSend(Map<String, Object> traceData) {
        Config config = Config.get();
        if (config == null) {
            logger.debug("No config available, skipping trace send");
            return;
        }

        try {
            String json = objectMapper.writeValueAsString(traceData);

            HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(config.getTracesEndpoint()))
                .timeout(Duration.ofMillis(config.getTimeoutMs()))
                .header("Content-Type", "application/json")
                .header("Authorization", config.getAuthHeader())
                .header("X-SDK-Version", Version.SDK_IDENTIFIER)
                .POST(HttpRequest.BodyPublishers.ofString(json))
                .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

            int status = response.statusCode();
            if (status >= 200 && status < 300) {
                logger.debug("Trace sent successfully ({})", status);
            } else {
                logger.warn("Trace ingestion failed: HTTP {} — {}", status, response.body());
            }
        } catch (Exception e) {
            logger.debug("Failed to send trace: {}", e.getMessage());
        }
    }

    // --- Global singleton ---

    public static void set(Transport transport) {
        instance = transport;
    }

    public static Transport get() {
        return instance;
    }

    public static void clear() {
        if (instance != null) {
            instance.stop();
        }
        instance = null;
    }
}

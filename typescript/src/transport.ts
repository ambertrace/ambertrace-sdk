/**
 * Async HTTP transport for sending traces to AmberTrace backend.
 *
 * Handles:
 * - Non-blocking trace delivery using async/await
 * - Bounded queue to prevent memory leaks
 * - Silent failure handling (never throws)
 * - Graceful shutdown with flush support
 * - HTTP POST with Bearer token authentication
 */

import fetch from 'node-fetch';
import type { Trace } from './models';
import { serializeTrace } from './models';
import { getConfig } from './config';

/**
 * Maximum number of traces to queue before dropping oldest.
 * Prevents unbounded memory growth if backend is slow/unavailable.
 */
const MAX_QUEUE_SIZE = 1000;

/**
 * Manages async delivery of traces to AmberTrace backend.
 */
export class Transport {
  private pendingTraces: Set<Promise<void>> = new Set();
  private droppedCount = 0;

  /**
   * Send a trace to the backend asynchronously.
   *
   * This method:
   * - Never blocks the caller
   * - Never throws exceptions
   * - Tracks pending requests for flush support
   * - Drops traces if queue is full
   *
   * @param trace - Trace object to send
   */
  sendTrace(trace: Trace): void {
    // Check queue size
    if (this.pendingTraces.size >= MAX_QUEUE_SIZE) {
      this.droppedCount++;
      if (getConfig()?.debug) {
        console.warn(
          `[AmberTrace] Trace queue full (${MAX_QUEUE_SIZE}), dropping trace ${trace.trace_id}`
        );
      }
      return;
    }

    // Send trace asynchronously
    const promise = this.sendTraceAsync(trace).finally(() => {
      // Remove from pending set when done
      this.pendingTraces.delete(promise);
    });

    this.pendingTraces.add(promise);
  }

  /**
   * Internal async method to send trace via HTTP POST.
   *
   * @param trace - Trace object to send
   */
  private async sendTraceAsync(trace: Trace): Promise<void> {
    const config = getConfig();
    if (!config) {
      if (trace) {
        console.error('[AmberTrace] Cannot send trace: SDK not initialized');
      }
      return;
    }

    try {
      const endpoint = config.getTraceEndpoint();
      const payload = serializeTrace(trace);

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: config.getAuthHeader(),
          'User-Agent': `ambertrace-node/${trace.sdk_version}`,
        },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(config.timeout),
      });

      if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown error');
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      if (config.debug) {
        console.log(`[AmberTrace] Trace ${trace.trace_id} sent successfully`);
      }
    } catch (error) {
      // Silent failure - log error but don't throw
      if (config?.debug) {
        console.error(`[AmberTrace] Failed to send trace ${trace.trace_id}:`, error);
      }
    }
  }

  /**
   * Wait for all pending traces to be sent.
   *
   * @param timeoutMs - Maximum time to wait in milliseconds (default: 5000)
   * @returns Promise that resolves when all traces are sent or timeout occurs
   */
  async flush(timeoutMs: number = 5000): Promise<void> {
    if (this.pendingTraces.size === 0) {
      return;
    }

    const config = getConfig();
    if (config?.debug) {
      console.log(`[AmberTrace] Flushing ${this.pendingTraces.size} pending traces...`);
    }

    try {
      // Create array of pending promises
      const pending = Array.from(this.pendingTraces);

      // Wait for all with timeout
      await Promise.race([
        Promise.all(pending),
        new Promise((resolve) => setTimeout(resolve, timeoutMs)),
      ]);

      if (config?.debug) {
        const remaining = this.pendingTraces.size;
        if (remaining > 0) {
          console.warn(`[AmberTrace] Flush timeout, ${remaining} traces still pending`);
        } else {
          console.log('[AmberTrace] All traces flushed successfully');
        }
      }
    } catch (error) {
      // Silent failure
      if (config?.debug) {
        console.error('[AmberTrace] Error during flush:', error);
      }
    }
  }

  /**
   * Get number of pending traces.
   */
  getPendingCount(): number {
    return this.pendingTraces.size;
  }

  /**
   * Get number of dropped traces (due to queue overflow).
   */
  getDroppedCount(): number {
    return this.droppedCount;
  }

  /**
   * Reset dropped count (for testing).
   */
  resetDroppedCount(): void {
    this.droppedCount = 0;
  }
}

// Global transport instance
let globalTransport: Transport | null = null;

/**
 * Get or create the global transport instance.
 */
export function getTransport(): Transport {
  if (!globalTransport) {
    globalTransport = new Transport();
  }
  return globalTransport;
}

/**
 * Clear the global transport instance.
 */
export function clearTransport(): void {
  globalTransport = null;
}

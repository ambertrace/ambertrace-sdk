"""Async transport for sending traces to backend."""

import asyncio
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from queue import Empty, Queue
from typing import Any, Dict, Optional

import httpx

from ambertrace.config import get_config

logger = logging.getLogger(__name__)


class Transport:
    """Handles async HTTP transport of traces to AmberTrace backend.

    Features:
    - Non-blocking trace delivery
    - Background thread pool for sync contexts
    - Asyncio tasks for async contexts
    - Bounded queue to prevent memory leaks
    - Silent failure handling (logs but never raises)
    """

    # Maximum number of traces to queue
    MAX_QUEUE_SIZE = 1000

    def __init__(self) -> None:
        """Initialize transport."""
        self._executor: Optional[ThreadPoolExecutor] = None
        self._queue: Queue[Dict[str, Any]] = Queue(maxsize=self.MAX_QUEUE_SIZE)
        self._shutdown = False
        self._lock = threading.Lock()
        self._pending_futures: list[Future] = []
        self._async_tasks: list[asyncio.Task] = []

    def start(self) -> None:
        """Start the transport (initialize thread pool)."""
        with self._lock:
            if self._executor is None:
                # Use small thread pool for background HTTP requests
                self._executor = ThreadPoolExecutor(
                    max_workers=2, thread_name_prefix="ambertrace-transport"
                )
                self._shutdown = False
                logger.debug("Transport started")

    def stop(self) -> None:
        """Stop the transport and cleanup resources."""
        with self._lock:
            if self._executor is not None:
                self._shutdown = True
                self._executor.shutdown(wait=False)
                self._executor = None
                logger.debug("Transport stopped")

    def send_trace(self, trace_dict: Dict[str, Any]) -> None:
        """Send a trace to the backend asynchronously.

        This method is non-blocking and never raises exceptions.

        Args:
            trace_dict: Serialized trace dictionary
        """
        if self._shutdown:
            logger.debug("Transport is shutdown, dropping trace")
            return

        try:
            # Try to add to queue (non-blocking)
            try:
                self._queue.put_nowait(trace_dict)
            except Exception:
                # Queue is full - drop oldest trace and try again
                try:
                    self._queue.get_nowait()
                    logger.warning("Trace queue full, dropped oldest trace")
                    self._queue.put_nowait(trace_dict)
                except Exception:
                    logger.warning("Failed to queue trace, dropping")
                    return

            # Submit to thread pool for async processing
            if self._executor is not None:
                future = self._executor.submit(self._send_trace_sync, trace_dict)
                with self._lock:
                    self._pending_futures.append(future)
            else:
                logger.warning("Transport not started, dropping trace")

        except Exception as e:
            # Never raise - just log
            logger.error(f"Failed to send trace: {e}", exc_info=True)

    def send_trace_async(self, trace_dict: Dict[str, Any]) -> None:
        """Send a trace from async context.

        Creates an asyncio task to send the trace.

        Args:
            trace_dict: Serialized trace dictionary
        """
        if self._shutdown:
            logger.debug("Transport is shutdown, dropping trace")
            return

        try:
            # Create asyncio task
            task = asyncio.create_task(self._send_trace_async(trace_dict))
            with self._lock:
                self._async_tasks.append(task)
                # Clean up completed tasks
                self._async_tasks = [t for t in self._async_tasks if not t.done()]

        except Exception as e:
            # Never raise - just log
            logger.error(f"Failed to send trace async: {e}", exc_info=True)

    def _send_trace_sync(self, trace_dict: Dict[str, Any]) -> None:
        """Send trace synchronously (called from thread pool).

        Args:
            trace_dict: Serialized trace dictionary
        """
        try:
            config = get_config()
            if not config:
                logger.warning("No configuration available, dropping trace")
                return

            # Create HTTP client
            with httpx.Client(timeout=config.timeout) as client:
                # Send POST request
                response = client.post(
                    config.traces_endpoint,
                    json=trace_dict,
                    headers={
                        "Authorization": f"Bearer {config.api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": f"ambertrace-python/{trace_dict.get('sdk_version', 'unknown')}",
                    },
                )

                # Check response
                if response.status_code == 201:
                    logger.debug(f"Trace {trace_dict.get('trace_id')} sent successfully")
                elif response.status_code == 401:
                    logger.error("Invalid API key - disabling tracing")
                    # Could trigger global disable here
                elif response.status_code == 400:
                    logger.error(f"Invalid trace data: {response.text}")
                elif response.status_code == 429:
                    logger.warning("Rate limit exceeded, trace dropped")
                elif response.status_code >= 500:
                    logger.warning(f"Server error ({response.status_code}), trace dropped")
                else:
                    logger.warning(
                        f"Unexpected response ({response.status_code}), trace dropped"
                    )

        except httpx.TimeoutException:
            logger.warning(f"Timeout sending trace {trace_dict.get('trace_id')}, dropped")
        except httpx.HTTPError as e:
            logger.warning(f"HTTP error sending trace: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending trace: {e}", exc_info=True)

    async def _send_trace_async(self, trace_dict: Dict[str, Any]) -> None:
        """Send trace asynchronously (async context).

        Args:
            trace_dict: Serialized trace dictionary
        """
        try:
            config = get_config()
            if not config:
                logger.warning("No configuration available, dropping trace")
                return

            # Create async HTTP client
            async with httpx.AsyncClient(timeout=config.timeout) as client:
                # Send POST request
                response = await client.post(
                    config.traces_endpoint,
                    json=trace_dict,
                    headers={
                        "Authorization": f"Bearer {config.api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": f"ambertrace-python/{trace_dict.get('sdk_version', 'unknown')}",
                    },
                )

                # Check response
                if response.status_code == 201:
                    logger.debug(f"Trace {trace_dict.get('trace_id')} sent successfully")
                elif response.status_code == 401:
                    logger.error("Invalid API key - disabling tracing")
                elif response.status_code == 400:
                    logger.error(f"Invalid trace data: {response.text}")
                elif response.status_code == 429:
                    logger.warning("Rate limit exceeded, trace dropped")
                elif response.status_code >= 500:
                    logger.warning(f"Server error ({response.status_code}), trace dropped")
                else:
                    logger.warning(
                        f"Unexpected response ({response.status_code}), trace dropped"
                    )

        except httpx.TimeoutException:
            logger.warning(f"Timeout sending trace {trace_dict.get('trace_id')}, dropped")
        except httpx.HTTPError as e:
            logger.warning(f"HTTP error sending trace: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending trace: {e}", exc_info=True)

    def flush(self, timeout: float = 5.0) -> None:
        """Wait for pending traces to be sent (blocking).

        Args:
            timeout: Maximum time to wait in seconds
        """
        try:
            import time

            start = time.time()

            # Wait for futures with timeout
            with self._lock:
                futures = list(self._pending_futures)

            for future in futures:
                remaining = timeout - (time.time() - start)
                if remaining <= 0:
                    logger.warning("Flush timeout reached, some traces may not be sent")
                    break

                try:
                    future.result(timeout=remaining)
                except Exception:
                    pass  # Already logged in the worker

            logger.debug("Flush completed")

        except Exception as e:
            logger.error(f"Error during flush: {e}", exc_info=True)

    async def flush_async(self, timeout: float = 5.0) -> None:
        """Wait for pending async traces to be sent (async context).

        Args:
            timeout: Maximum time to wait in seconds
        """
        try:
            # Get current tasks
            with self._lock:
                tasks = list(self._async_tasks)

            if tasks:
                # Wait for tasks with timeout
                done, pending = await asyncio.wait(tasks, timeout=timeout)

                if pending:
                    logger.warning(
                        f"Flush timeout reached, {len(pending)} traces may not be sent"
                    )

            logger.debug("Async flush completed")

        except Exception as e:
            logger.error(f"Error during async flush: {e}", exc_info=True)


# Global transport instance
_global_transport: Optional[Transport] = None


def get_transport() -> Optional[Transport]:
    """Get the global transport instance."""
    return _global_transport


def set_transport(transport: Transport) -> None:
    """Set the global transport instance."""
    global _global_transport
    _global_transport = transport

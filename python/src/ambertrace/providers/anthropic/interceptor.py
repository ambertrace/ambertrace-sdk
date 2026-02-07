"""Anthropic SDK interception via monkey-patching."""

import functools
import logging
import time
import uuid
from typing import Any, Callable, Optional

from ambertrace.providers.anthropic.collector import AnthropicCollector
from ambertrace.providers.base import BaseInterceptor
from ambertrace.transport import get_transport

logger = logging.getLogger(__name__)


class AnthropicInterceptor(BaseInterceptor):
    """Handles monkey-patching of Anthropic SDK methods.

    This class wraps Anthropic client methods to intercept calls and collect traces.
    The wrapping is transparent - all original behavior is preserved exactly.
    """

    def __init__(self) -> None:
        """Initialize interceptor."""
        self._original_sync_create: Optional[Callable] = None
        self._original_async_create: Optional[Callable] = None
        self._is_patched = False
        self._collector = AnthropicCollector()

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "anthropic"

    def patch(self) -> None:
        """Apply monkey-patches to Anthropic SDK methods.

        Wraps:
        - anthropic.Anthropic.messages.create (sync)
        - anthropic.AsyncAnthropic.messages.create (async)
        """
        if self._is_patched:
            logger.debug("Anthropic already patched, skipping")
            return

        try:
            import anthropic

            # Patch sync method
            if hasattr(anthropic, "Anthropic"):
                try:
                    # Navigate to messages.create
                    # We need to patch at the resources level
                    if hasattr(anthropic.resources, "Messages"):
                        messages_class = anthropic.resources.Messages

                        if hasattr(messages_class, "create"):
                            self._original_sync_create = messages_class.create
                            messages_class.create = self._wrap_sync_create(
                                self._original_sync_create
                            )
                            logger.debug("Patched Anthropic.messages.create (sync)")
                        else:
                            logger.warning("Could not find create method on Messages class")
                    else:
                        logger.warning("Could not find Messages resources")

                except Exception as e:
                    logger.error(f"Failed to patch sync Anthropic method: {e}", exc_info=True)

            # Patch async method
            if hasattr(anthropic, "AsyncAnthropic"):
                try:
                    # Navigate to async messages.create
                    if hasattr(anthropic.resources, "AsyncMessages"):
                        async_messages_class = anthropic.resources.AsyncMessages

                        if hasattr(async_messages_class, "create"):
                            self._original_async_create = async_messages_class.create
                            async_messages_class.create = self._wrap_async_create(
                                self._original_async_create
                            )
                            logger.debug("Patched AsyncAnthropic.messages.create (async)")
                        else:
                            logger.warning("Could not find create method on AsyncMessages class")
                    else:
                        logger.warning("Could not find AsyncMessages resources")

                except Exception as e:
                    logger.error(f"Failed to patch async Anthropic method: {e}", exc_info=True)

            self._is_patched = True
            logger.info("Anthropic SDK patching completed")

        except ImportError:
            logger.warning("Anthropic SDK not found - skipping Anthropic tracing")
        except Exception as e:
            logger.error(f"Unexpected error during Anthropic patching: {e}", exc_info=True)

    def unpatch(self) -> None:
        """Remove monkey-patches and restore original Anthropic methods."""
        if not self._is_patched:
            logger.debug("Anthropic not patched, skipping unpatch")
            return

        try:
            import anthropic

            # Restore sync method
            if self._original_sync_create is not None:
                try:
                    if hasattr(anthropic.resources, "Messages"):
                        anthropic.resources.Messages.create = self._original_sync_create
                        logger.debug("Restored original Anthropic sync create method")
                except Exception as e:
                    logger.error(f"Failed to restore Anthropic sync method: {e}", exc_info=True)

            # Restore async method
            if self._original_async_create is not None:
                try:
                    if hasattr(anthropic.resources, "AsyncMessages"):
                        anthropic.resources.AsyncMessages.create = self._original_async_create
                        logger.debug("Restored original Anthropic async create method")
                except Exception as e:
                    logger.error(f"Failed to restore Anthropic async method: {e}", exc_info=True)

            self._is_patched = False
            self._original_sync_create = None
            self._original_async_create = None
            logger.info("Anthropic SDK unpatching completed")

        except Exception as e:
            logger.error(f"Unexpected error during Anthropic unpatching: {e}", exc_info=True)

    def is_patched(self) -> bool:
        """Check if patches are currently applied."""
        return self._is_patched

    def _wrap_sync_create(self, original_method: Callable) -> Callable:
        """Create wrapper for sync messages.create method.

        Args:
            original_method: Original Anthropic method to wrap

        Returns:
            Wrapped method that collects traces
        """

        @functools.wraps(original_method)
        def wrapper(self_instance: Any, *args: Any, **kwargs: Any) -> Any:
            """Wrapper that intercepts sync Anthropic calls."""
            trace_id = str(uuid.uuid4())
            start_time = time.time()

            try:
                # Call original method
                response = original_method(self_instance, *args, **kwargs)

                # Collect trace (non-blocking, never raises)
                try:
                    trace_dict = self._collector.collect_trace(
                        trace_id=trace_id,
                        start_time=start_time,
                        request_kwargs=kwargs,
                        response=response,
                        error=None,
                    )

                    if trace_dict:
                        transport = get_transport()
                        if transport:
                            transport.send_trace(trace_dict)
                except Exception as e:
                    # Never let trace collection errors affect user code
                    logger.error(f"Error collecting Anthropic trace {trace_id}: {e}", exc_info=True)

                # Return original response unchanged
                return response

            except Exception as e:
                # Collect trace with error information
                try:
                    trace_dict = self._collector.collect_trace(
                        trace_id=trace_id,
                        start_time=start_time,
                        request_kwargs=kwargs,
                        response=None,
                        error=e,
                    )

                    if trace_dict:
                        transport = get_transport()
                        if transport:
                            transport.send_trace(trace_dict)
                except Exception as trace_error:
                    logger.error(
                        f"Error collecting Anthropic error trace {trace_id}: {trace_error}",
                        exc_info=True,
                    )

                # Re-raise original exception to preserve user experience
                raise

        return wrapper

    def _wrap_async_create(self, original_method: Callable) -> Callable:
        """Create wrapper for async messages.create method.

        Args:
            original_method: Original async Anthropic method to wrap

        Returns:
            Wrapped async method that collects traces
        """

        @functools.wraps(original_method)
        async def wrapper(self_instance: Any, *args: Any, **kwargs: Any) -> Any:
            """Wrapper that intercepts async Anthropic calls."""
            trace_id = str(uuid.uuid4())
            start_time = time.time()

            try:
                # Await original method
                response = await original_method(self_instance, *args, **kwargs)

                # Collect trace (non-blocking, never raises)
                try:
                    trace_dict = self._collector.collect_trace(
                        trace_id=trace_id,
                        start_time=start_time,
                        request_kwargs=kwargs,
                        response=response,
                        error=None,
                    )

                    if trace_dict:
                        transport = get_transport()
                        if transport:
                            # Use async send for async context
                            transport.send_trace_async(trace_dict)
                except Exception as e:
                    # Never let trace collection errors affect user code
                    logger.error(f"Error collecting Anthropic trace {trace_id}: {e}", exc_info=True)

                # Return original response unchanged
                return response

            except Exception as e:
                # Collect trace with error information
                try:
                    trace_dict = self._collector.collect_trace(
                        trace_id=trace_id,
                        start_time=start_time,
                        request_kwargs=kwargs,
                        response=None,
                        error=e,
                    )

                    if trace_dict:
                        transport = get_transport()
                        if transport:
                            # Use async send for async context
                            transport.send_trace_async(trace_dict)
                except Exception as trace_error:
                    logger.error(
                        f"Error collecting Anthropic error trace {trace_id}: {trace_error}",
                        exc_info=True,
                    )

                # Re-raise original exception to preserve user experience
                raise

        return wrapper

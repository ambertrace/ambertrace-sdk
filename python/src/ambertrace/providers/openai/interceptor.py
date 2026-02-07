"""OpenAI SDK interception via monkey-patching."""

import functools
import logging
import time
import uuid
from typing import Any, Callable, Optional

from ambertrace.providers.base import BaseInterceptor
from ambertrace.providers.openai.collector import OpenAICollector
from ambertrace.transport import get_transport

logger = logging.getLogger(__name__)


class OpenAIInterceptor(BaseInterceptor):
    """Handles monkey-patching of OpenAI SDK methods.

    This class wraps OpenAI client methods to intercept calls and collect traces.
    The wrapping is transparent - all original behavior is preserved exactly.
    """

    def __init__(self) -> None:
        """Initialize interceptor."""
        self._original_sync_create: Optional[Callable] = None
        self._original_async_create: Optional[Callable] = None
        self._is_patched = False
        self._collector = OpenAICollector()

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "openai"

    def patch(self) -> None:
        """Apply monkey-patches to OpenAI SDK methods.

        Wraps:
        - openai.OpenAI.chat.completions.create (sync)
        - openai.AsyncOpenAI.chat.completions.create (async)
        """
        if self._is_patched:
            logger.debug("OpenAI already patched, skipping")
            return

        try:
            import openai

            # Patch sync method
            if hasattr(openai, "OpenAI"):
                try:
                    # Navigate to chat.completions.create
                    # We need to patch at the resources level
                    if hasattr(openai.resources, "chat") and hasattr(
                        openai.resources.chat, "Completions"
                    ):
                        completions_class = openai.resources.chat.Completions

                        if hasattr(completions_class, "create"):
                            self._original_sync_create = completions_class.create
                            completions_class.create = self._wrap_sync_create(
                                self._original_sync_create
                            )
                            logger.debug("Patched OpenAI.chat.completions.create (sync)")
                        else:
                            logger.warning("Could not find create method on Completions class")
                    else:
                        logger.warning("Could not find chat.Completions resources")

                except Exception as e:
                    logger.error(f"Failed to patch sync OpenAI method: {e}", exc_info=True)

            # Patch async method
            if hasattr(openai, "AsyncOpenAI"):
                try:
                    # Navigate to async chat.completions.create
                    if hasattr(openai.resources.chat, "AsyncCompletions"):
                        async_completions_class = openai.resources.chat.AsyncCompletions

                        if hasattr(async_completions_class, "create"):
                            self._original_async_create = async_completions_class.create
                            async_completions_class.create = self._wrap_async_create(
                                self._original_async_create
                            )
                            logger.debug("Patched AsyncOpenAI.chat.completions.create (async)")
                        else:
                            logger.warning("Could not find create method on AsyncCompletions class")
                    else:
                        logger.warning("Could not find chat.AsyncCompletions resources")

                except Exception as e:
                    logger.error(f"Failed to patch async OpenAI method: {e}", exc_info=True)

            self._is_patched = True
            logger.info("OpenAI SDK patching completed")

        except ImportError:
            logger.warning("OpenAI SDK not found - skipping OpenAI tracing")
        except Exception as e:
            logger.error(f"Unexpected error during OpenAI patching: {e}", exc_info=True)

    def unpatch(self) -> None:
        """Remove monkey-patches and restore original OpenAI methods."""
        if not self._is_patched:
            logger.debug("OpenAI not patched, skipping unpatch")
            return

        try:
            import openai

            # Restore sync method
            if self._original_sync_create is not None:
                try:
                    if hasattr(openai.resources.chat, "Completions"):
                        openai.resources.chat.Completions.create = self._original_sync_create
                        logger.debug("Restored original OpenAI sync create method")
                except Exception as e:
                    logger.error(f"Failed to restore OpenAI sync method: {e}", exc_info=True)

            # Restore async method
            if self._original_async_create is not None:
                try:
                    if hasattr(openai.resources.chat, "AsyncCompletions"):
                        openai.resources.chat.AsyncCompletions.create = self._original_async_create
                        logger.debug("Restored original OpenAI async create method")
                except Exception as e:
                    logger.error(f"Failed to restore OpenAI async method: {e}", exc_info=True)

            self._is_patched = False
            self._original_sync_create = None
            self._original_async_create = None
            logger.info("OpenAI SDK unpatching completed")

        except Exception as e:
            logger.error(f"Unexpected error during OpenAI unpatching: {e}", exc_info=True)

    def is_patched(self) -> bool:
        """Check if patches are currently applied."""
        return self._is_patched

    def _wrap_sync_create(self, original_method: Callable) -> Callable:
        """Create wrapper for sync chat.completions.create method.

        Args:
            original_method: Original OpenAI method to wrap

        Returns:
            Wrapped method that collects traces
        """

        @functools.wraps(original_method)
        def wrapper(self_instance: Any, *args: Any, **kwargs: Any) -> Any:
            """Wrapper that intercepts sync OpenAI calls."""
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
                    logger.error(f"Error collecting OpenAI trace {trace_id}: {e}", exc_info=True)

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
                        f"Error collecting OpenAI error trace {trace_id}: {trace_error}",
                        exc_info=True,
                    )

                # Re-raise original exception to preserve user experience
                raise

        return wrapper

    def _wrap_async_create(self, original_method: Callable) -> Callable:
        """Create wrapper for async chat.completions.create method.

        Args:
            original_method: Original async OpenAI method to wrap

        Returns:
            Wrapped async method that collects traces
        """

        @functools.wraps(original_method)
        async def wrapper(self_instance: Any, *args: Any, **kwargs: Any) -> Any:
            """Wrapper that intercepts async OpenAI calls."""
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
                    logger.error(f"Error collecting OpenAI trace {trace_id}: {e}", exc_info=True)

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
                        f"Error collecting OpenAI error trace {trace_id}: {trace_error}",
                        exc_info=True,
                    )

                # Re-raise original exception to preserve user experience
                raise

        return wrapper

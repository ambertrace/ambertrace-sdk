"""Google Gemini SDK interception via monkey-patching.

Supports both Gemini SDKs:
- google-generativeai (original): patches GenerativeModel.generate_content
- google-genai (newer): patches the models resource generate_content
"""

import functools
import logging
import time
import uuid
from typing import Any, Callable, Optional

from ambertrace.providers.base import BaseInterceptor
from ambertrace.providers.gemini.collector import GeminiCollector
from ambertrace.transport import get_transport

logger = logging.getLogger(__name__)


class GeminiInterceptor(BaseInterceptor):
    """Handles monkey-patching of Google Gemini SDK methods.

    Supports both the original google-generativeai SDK and the newer
    google-genai SDK. Each is patched independently.
    """

    def __init__(self) -> None:
        """Initialize interceptor."""
        # Original SDK (google-generativeai)
        self._original_genai_sync: Optional[Callable] = None
        self._original_genai_async: Optional[Callable] = None
        self._genai_patched = False

        # Newer SDK (google-genai)
        self._original_genai2_sync: Optional[Callable] = None
        self._original_genai2_async: Optional[Callable] = None
        self._genai2_patched = False

        self._collector = GeminiCollector()

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "gemini"

    def patch(self) -> None:
        """Apply monkey-patches to Gemini SDK methods.

        Attempts to patch both Gemini SDKs independently. If only one
        is installed, only that one is patched.
        """
        if self._genai_patched and self._genai2_patched:
            logger.debug("Gemini already fully patched, skipping")
            return

        # --- Original SDK: google.generativeai ---
        if not self._genai_patched:
            try:
                import google.generativeai as genai

                model_class = genai.GenerativeModel

                # Patch sync: GenerativeModel.generate_content
                if hasattr(model_class, "generate_content"):
                    self._original_genai_sync = model_class.generate_content
                    model_class.generate_content = self._wrap_genai_sync(
                        self._original_genai_sync
                    )
                    logger.debug("Patched GenerativeModel.generate_content (sync)")

                # Patch async: GenerativeModel.generate_content_async
                if hasattr(model_class, "generate_content_async"):
                    self._original_genai_async = model_class.generate_content_async
                    model_class.generate_content_async = self._wrap_genai_async(
                        self._original_genai_async
                    )
                    logger.debug("Patched GenerativeModel.generate_content_async (async)")

                self._genai_patched = True
                logger.info("google-generativeai SDK patching completed")

            except ImportError:
                logger.debug("google-generativeai SDK not found, skipping")
            except Exception as e:
                logger.error(f"Failed to patch google-generativeai: {e}", exc_info=True)

        # --- Newer SDK: google.genai ---
        if not self._genai2_patched:
            try:
                from google import genai  # noqa: F811

                # The newer SDK uses client.models.generate_content()
                # We need to find the Models resource class
                models_module = genai.models if hasattr(genai, "models") else None

                if models_module is not None:
                    # Try to find the Models class
                    models_class = None
                    if hasattr(models_module, "Models"):
                        models_class = models_module.Models
                    elif hasattr(models_module, "AsyncModels"):
                        # Try to get the sync class from the module
                        for attr_name in dir(models_module):
                            attr = getattr(models_module, attr_name)
                            if (
                                isinstance(attr, type)
                                and hasattr(attr, "generate_content")
                                and attr_name != "AsyncModels"
                            ):
                                models_class = attr
                                break

                    if models_class and hasattr(models_class, "generate_content"):
                        self._original_genai2_sync = models_class.generate_content
                        models_class.generate_content = self._wrap_genai2_sync(
                            self._original_genai2_sync
                        )
                        logger.debug("Patched google.genai Models.generate_content (sync)")

                    # Try to patch async variant
                    async_models_class = None
                    if hasattr(models_module, "AsyncModels"):
                        async_models_class = models_module.AsyncModels

                    if async_models_class and hasattr(async_models_class, "generate_content"):
                        self._original_genai2_async = async_models_class.generate_content
                        async_models_class.generate_content = self._wrap_genai2_async(
                            self._original_genai2_async
                        )
                        logger.debug("Patched google.genai AsyncModels.generate_content (async)")

                    self._genai2_patched = True
                    logger.info("google-genai SDK patching completed")
                else:
                    logger.warning("Could not find models module in google.genai")

            except ImportError:
                logger.debug("google-genai SDK not found, skipping")
            except Exception as e:
                logger.error(f"Failed to patch google-genai: {e}", exc_info=True)

        if self.is_patched():
            logger.info("Gemini SDK patching completed")

    def unpatch(self) -> None:
        """Remove monkey-patches and restore original Gemini methods."""
        # Restore original SDK (google-generativeai)
        if self._genai_patched:
            try:
                import google.generativeai as genai

                model_class = genai.GenerativeModel

                if self._original_genai_sync is not None:
                    model_class.generate_content = self._original_genai_sync
                    logger.debug("Restored GenerativeModel.generate_content (sync)")

                if self._original_genai_async is not None:
                    model_class.generate_content_async = self._original_genai_async
                    logger.debug("Restored GenerativeModel.generate_content_async (async)")

                self._genai_patched = False
                self._original_genai_sync = None
                self._original_genai_async = None
                logger.info("google-generativeai SDK unpatching completed")

            except Exception as e:
                logger.error(
                    f"Failed to unpatch google-generativeai: {e}", exc_info=True
                )

        # Restore newer SDK (google-genai)
        if self._genai2_patched:
            try:
                from google import genai

                models_module = genai.models if hasattr(genai, "models") else None

                if models_module is not None:
                    if self._original_genai2_sync is not None:
                        models_class = None
                        if hasattr(models_module, "Models"):
                            models_class = models_module.Models
                        if models_class:
                            models_class.generate_content = self._original_genai2_sync
                            logger.debug("Restored google.genai Models.generate_content")

                    if self._original_genai2_async is not None:
                        async_models_class = None
                        if hasattr(models_module, "AsyncModels"):
                            async_models_class = models_module.AsyncModels
                        if async_models_class:
                            async_models_class.generate_content = self._original_genai2_async
                            logger.debug("Restored google.genai AsyncModels.generate_content")

                self._genai2_patched = False
                self._original_genai2_sync = None
                self._original_genai2_async = None
                logger.info("google-genai SDK unpatching completed")

            except Exception as e:
                logger.error(f"Failed to unpatch google-genai: {e}", exc_info=True)

    def is_patched(self) -> bool:
        """Check if patches are currently applied."""
        return self._genai_patched or self._genai2_patched

    # --- Wrappers for original SDK (google-generativeai) ---

    def _wrap_genai_sync(self, original_method: Callable) -> Callable:
        """Create wrapper for sync GenerativeModel.generate_content.

        The original SDK stores the model name on the instance, not in
        method arguments. The wrapper extracts it and injects it as
        _ambertrace_model for the collector.
        """

        @functools.wraps(original_method)
        def wrapper(self_instance: Any, *args: Any, **kwargs: Any) -> Any:
            trace_id = str(uuid.uuid4())
            start_time = time.time()

            # Extract model name from the GenerativeModel instance
            model_name = getattr(self_instance, "model_name", None) or getattr(
                self_instance, "_model_name", "unknown"
            )

            # Build enriched kwargs for the collector
            enriched_kwargs = {**kwargs, "_ambertrace_model": model_name}
            # Capture contents from positional args if not in kwargs
            if args and "contents" not in enriched_kwargs:
                enriched_kwargs["contents"] = args[0]

            try:
                response = original_method(self_instance, *args, **kwargs)

                try:
                    trace_dict = self._collector.collect_trace(
                        trace_id=trace_id,
                        start_time=start_time,
                        request_kwargs=enriched_kwargs,
                        response=response,
                        error=None,
                    )
                    if trace_dict:
                        transport = get_transport()
                        if transport:
                            transport.send_trace(trace_dict)
                except Exception as e:
                    logger.error(
                        f"Error collecting Gemini trace {trace_id}: {e}", exc_info=True
                    )

                return response

            except Exception as e:
                try:
                    trace_dict = self._collector.collect_trace(
                        trace_id=trace_id,
                        start_time=start_time,
                        request_kwargs=enriched_kwargs,
                        response=None,
                        error=e,
                    )
                    if trace_dict:
                        transport = get_transport()
                        if transport:
                            transport.send_trace(trace_dict)
                except Exception as trace_error:
                    logger.error(
                        f"Error collecting Gemini error trace {trace_id}: {trace_error}",
                        exc_info=True,
                    )
                raise

        return wrapper

    def _wrap_genai_async(self, original_method: Callable) -> Callable:
        """Create wrapper for async GenerativeModel.generate_content_async."""

        @functools.wraps(original_method)
        async def wrapper(self_instance: Any, *args: Any, **kwargs: Any) -> Any:
            trace_id = str(uuid.uuid4())
            start_time = time.time()

            model_name = getattr(self_instance, "model_name", None) or getattr(
                self_instance, "_model_name", "unknown"
            )
            enriched_kwargs = {**kwargs, "_ambertrace_model": model_name}
            if args and "contents" not in enriched_kwargs:
                enriched_kwargs["contents"] = args[0]

            try:
                response = await original_method(self_instance, *args, **kwargs)

                try:
                    trace_dict = self._collector.collect_trace(
                        trace_id=trace_id,
                        start_time=start_time,
                        request_kwargs=enriched_kwargs,
                        response=response,
                        error=None,
                    )
                    if trace_dict:
                        transport = get_transport()
                        if transport:
                            transport.send_trace_async(trace_dict)
                except Exception as e:
                    logger.error(
                        f"Error collecting Gemini trace {trace_id}: {e}", exc_info=True
                    )

                return response

            except Exception as e:
                try:
                    trace_dict = self._collector.collect_trace(
                        trace_id=trace_id,
                        start_time=start_time,
                        request_kwargs=enriched_kwargs,
                        response=None,
                        error=e,
                    )
                    if trace_dict:
                        transport = get_transport()
                        if transport:
                            transport.send_trace_async(trace_dict)
                except Exception as trace_error:
                    logger.error(
                        f"Error collecting Gemini error trace {trace_id}: {trace_error}",
                        exc_info=True,
                    )
                raise

        return wrapper

    # --- Wrappers for newer SDK (google-genai) ---

    def _wrap_genai2_sync(self, original_method: Callable) -> Callable:
        """Create wrapper for google.genai Models.generate_content.

        The newer SDK passes model as a kwarg:
            client.models.generate_content(model="gemini-2.0-flash", contents="Hello")
        """

        @functools.wraps(original_method)
        def wrapper(self_instance: Any, *args: Any, **kwargs: Any) -> Any:
            trace_id = str(uuid.uuid4())
            start_time = time.time()

            try:
                response = original_method(self_instance, *args, **kwargs)

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
                    logger.error(
                        f"Error collecting Gemini trace {trace_id}: {e}", exc_info=True
                    )

                return response

            except Exception as e:
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
                        f"Error collecting Gemini error trace {trace_id}: {trace_error}",
                        exc_info=True,
                    )
                raise

        return wrapper

    def _wrap_genai2_async(self, original_method: Callable) -> Callable:
        """Create wrapper for google.genai AsyncModels.generate_content."""

        @functools.wraps(original_method)
        async def wrapper(self_instance: Any, *args: Any, **kwargs: Any) -> Any:
            trace_id = str(uuid.uuid4())
            start_time = time.time()

            try:
                response = await original_method(self_instance, *args, **kwargs)

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
                            transport.send_trace_async(trace_dict)
                except Exception as e:
                    logger.error(
                        f"Error collecting Gemini trace {trace_id}: {e}", exc_info=True
                    )

                return response

            except Exception as e:
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
                            transport.send_trace_async(trace_dict)
                except Exception as trace_error:
                    logger.error(
                        f"Error collecting Gemini error trace {trace_id}: {trace_error}",
                        exc_info=True,
                    )
                raise

        return wrapper

"""AmberTrace Python SDK - LLM observability for OpenAI, Anthropic, and Google.

This SDK provides automatic tracing of LLM API calls with minimal configuration.

Basic usage:
    import openai
    import ambertrace

    # Initialize tracing
    ambertrace.init(api_key="your_api_key")

    # Use OpenAI SDK normally - calls are traced automatically
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )

    # Optional: flush pending traces before exit
    ambertrace.flush()
"""

import asyncio
import logging
from typing import Optional

from ambertrace._version import __version__
from ambertrace.config import Config, get_config, is_configured, set_config
from ambertrace.providers.registry import ProviderRegistry, get_registry, set_registry
from ambertrace.transport import Transport, get_transport, set_transport

__all__ = [
    "__version__",
    "init",
    "enable",
    "disable",
    "is_enabled",
    "flush",
    "flush_async",
    "new_session",
]

logger = logging.getLogger(__name__)


def init(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    environment: Optional[str] = None,
    debug: Optional[bool] = None,
    timeout: Optional[float] = None,
    enabled: Optional[bool] = None,
    service_name: Optional[str] = None,
) -> None:
    """Initialize AmberTrace SDK.

    This function must be called before using LLM SDKs to enable tracing.
    After initialization, all supported LLM calls are automatically traced.

    Supported providers (auto-detected):
    - OpenAI (if openai package is installed)
    - Anthropic (if anthropic package is installed)
    - Google (if google-generativeai or google-genai package is installed)

    Args:
        api_key: AmberTrace API key (or set AMBERTRACE_API_KEY env var)
        base_url: Backend API URL (default: https://api.ambertrace.dev)
        environment: Environment tag for traces (e.g., "production", "staging")
        debug: Enable debug logging (default: False)
        timeout: Network timeout in seconds (default: 5.0)
        enabled: Enable/disable tracing (default: True)
        service_name: Name of the client app sending traces (e.g., "my-chatbot")

    Raises:
        ValueError: If no API key is provided

    Example:
        >>> import ambertrace
        >>> ambertrace.init(api_key="at_1234567890abcdef")
        >>> # All supported LLM SDK calls are now traced automatically
    """
    try:
        # Create configuration
        config = Config(
            api_key=api_key,
            base_url=base_url,
            environment=environment,
            debug=debug,
            timeout=timeout,
            enabled=enabled,
            service_name=service_name,
        )
        set_config(config)

        logger.debug(f"Initialized with config: {config}")

        # Only proceed if enabled
        if not config.enabled:
            logger.info("AmberTrace initialized but disabled (enabled=False)")
            return

        # Create provider registry
        registry = ProviderRegistry()

        # Auto-detect and register OpenAI if available
        try:
            import openai  # noqa: F401

            from ambertrace.providers.openai import OpenAICollector, OpenAIInterceptor

            registry.register_provider("openai", OpenAIInterceptor(), OpenAICollector())
            logger.debug("Registered OpenAI provider")
        except ImportError:
            logger.info("OpenAI SDK not found, skipping OpenAI tracing")

        # Auto-detect and register Anthropic if available
        try:
            import anthropic  # noqa: F401

            from ambertrace.providers.anthropic import AnthropicCollector, AnthropicInterceptor

            registry.register_provider(
                "anthropic", AnthropicInterceptor(), AnthropicCollector()
            )
            logger.debug("Registered Anthropic provider")
        except ImportError:
            logger.info("Anthropic SDK not found, skipping Anthropic tracing")

        # Auto-detect and register Google if available
        # Supports both google-generativeai (original) and google-genai (newer) SDKs
        try:
            _gemini_available = False
            try:
                import google.generativeai  # noqa: F401

                _gemini_available = True
            except ImportError:
                pass
            try:
                from google import genai  # noqa: F401

                _gemini_available = True
            except ImportError:
                pass

            if _gemini_available:
                from ambertrace.providers.gemini import GeminiCollector, GeminiInterceptor

                registry.register_provider(
                    "gemini", GeminiInterceptor(), GeminiCollector()
                )
                logger.debug("Registered Gemini provider")
            else:
                raise ImportError("No Gemini SDK found")
        except ImportError:
            logger.info("Google SDK not found, skipping Google tracing")

        # Check if any providers were registered
        registered_providers = registry.get_registered_providers()
        if not registered_providers:
            logger.warning(
                "No supported LLM SDKs found. Install 'openai', 'anthropic', "
                "'google-generativeai', or 'google-genai' package to enable tracing."
            )
            return

        # Create and start transport
        transport = Transport()
        transport.start()
        set_transport(transport)

        logger.debug("Transport started")

        # Patch all registered providers
        registry.patch_all()
        set_registry(registry)

        logger.info(
            f"AmberTrace SDK initialized successfully for providers: {registered_providers}"
        )

    except Exception as e:
        logger.error(f"Failed to initialize AmberTrace: {e}", exc_info=True)
        # Don't raise - allow user code to continue even if tracing fails
        logger.warning("AmberTrace initialization failed, tracing will be disabled")


def enable() -> None:
    """Enable tracing by re-applying monkey-patches.

    This can be used to re-enable tracing after calling disable().
    If init() has not been called yet, this function does nothing.

    Example:
        >>> ambertrace.disable()
        >>> # ... do something without tracing ...
        >>> ambertrace.enable()
    """
    try:
        if not is_configured():
            logger.warning("AmberTrace not initialized, call init() first")
            return

        config = get_config()
        if config and not config.enabled:
            logger.info("AmberTrace is disabled in config, not enabling")
            return

        # Get or create registry
        registry = get_registry()
        if registry is None:
            logger.warning("No provider registry found, call init() first")
            return

        # Apply patches for all providers
        registry.patch_all()
        logger.info("AmberTrace tracing enabled")

        # Get or create transport
        transport = get_transport()
        if transport is None:
            transport = Transport()
            transport.start()
            set_transport(transport)
        else:
            transport.start()

    except Exception as e:
        logger.error(f"Failed to enable AmberTrace: {e}", exc_info=True)


def disable() -> None:
    """Disable tracing by removing monkey-patches.

    This stops all trace collection. LLM SDK calls will work normally
    but will not be traced. The transport is also stopped.

    Call enable() to resume tracing.

    Example:
        >>> ambertrace.disable()
        >>> # LLM calls are no longer traced
    """
    try:
        # Remove patches from all providers
        registry = get_registry()
        if registry is not None:
            registry.unpatch_all()
            logger.info("AmberTrace tracing disabled")

        # Stop transport
        transport = get_transport()
        if transport is not None:
            transport.stop()

    except Exception as e:
        logger.error(f"Failed to disable AmberTrace: {e}", exc_info=True)


def is_enabled() -> bool:
    """Check if tracing is currently enabled.

    Returns:
        True if tracing is active for any provider, False otherwise

    Example:
        >>> if ambertrace.is_enabled():
        ...     print("Tracing is active")
    """
    try:
        registry = get_registry()
        return registry is not None and registry.is_patched()
    except Exception:
        return False


def flush(timeout: float = 5.0) -> None:
    """Wait for all pending traces to be sent (blocking).

    This should be called before your application exits to ensure
    all traces are delivered to the backend.

    Args:
        timeout: Maximum time to wait in seconds (default: 5.0)

    Example:
        >>> ambertrace.flush()
        >>> # All pending traces have been sent (or timeout reached)
    """
    try:
        transport = get_transport()
        if transport is not None:
            # Check if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context but flush() is sync
                # User should use flush_async() instead, but we'll try our best
                logger.warning(
                    "flush() called from async context, use 'await ambertrace.flush_async()' instead"
                )
                # Fall back to sync flush (will block the event loop - not ideal)
                transport.flush(timeout=timeout)
            except RuntimeError:
                # No running loop - we're in sync context (good)
                transport.flush(timeout=timeout)

            logger.debug("Flush completed")
        else:
            logger.debug("No transport to flush")

    except Exception as e:
        logger.error(f"Failed to flush traces: {e}", exc_info=True)


async def flush_async(timeout: float = 5.0) -> None:
    """Wait for all pending traces to be sent (async).

    Use this in async contexts instead of flush().

    Args:
        timeout: Maximum time to wait in seconds (default: 5.0)

    Example:
        >>> await ambertrace.flush_async()
        >>> # All pending traces have been sent (or timeout reached)
    """
    try:
        transport = get_transport()
        if transport is not None:
            await transport.flush_async(timeout=timeout)
            logger.debug("Async flush completed")
        else:
            logger.debug("No transport to flush")

    except Exception as e:
        logger.error(f"Failed to flush traces async: {e}", exc_info=True)


def new_session() -> Optional[str]:
    """Start a new trace session by rotating the trace_session_id.

    Useful for long-running apps (e.g., servers) that want to group
    traces into logical runs without restarting.

    Returns:
        The new trace_session_id, or None if not initialized.

    Example:
        >>> ambertrace.new_session()
        '20260318-bold-fox-4291'
    """
    try:
        config = get_config()
        if config is None:
            logger.warning("AmberTrace not initialized, call init() first")
            return None
        return config.new_session()
    except Exception as e:
        logger.error(f"Failed to create new session: {e}", exc_info=True)
        return None


# Export version
__version__ = __version__

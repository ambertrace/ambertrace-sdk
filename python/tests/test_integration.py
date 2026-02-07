"""Integration tests for AmberTrace SDK.

These tests verify the end-to-end flow with mocked OpenAI API.
"""

import asyncio
from unittest.mock import Mock

import httpx
import pytest
import respx

import ambertrace
from ambertrace.config import set_config
from ambertrace.providers.registry import set_registry
from ambertrace.transport import set_transport


class MockOpenAIClient:
    """Mock OpenAI client for testing."""

    def __init__(self):
        self.chat = Mock()
        self.chat.completions = Mock()
        self.chat.completions.create = self._create_sync

    def _create_sync(self, **kwargs):
        """Mock sync create method."""
        return Mock(
            id="chatcmpl-test",
            model=kwargs.get("model", "gpt-4"),
            choices=[
                Mock(
                    index=0,
                    message=Mock(role="assistant", content="Test response"),
                    finish_reason="stop",
                )
            ],
            usage=Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )


class MockAsyncOpenAIClient:
    """Mock AsyncOpenAI client for testing."""

    def __init__(self):
        self.chat = Mock()
        self.chat.completions = Mock()
        self.chat.completions.create = self._create_async

    async def _create_async(self, **kwargs):
        """Mock async create method."""
        return Mock(
            id="chatcmpl-test-async",
            model=kwargs.get("model", "gpt-4"),
            choices=[
                Mock(
                    index=0,
                    message=Mock(role="assistant", content="Async test response"),
                    finish_reason="stop",
                )
            ],
            usage=Mock(prompt_tokens=12, completion_tokens=8, total_tokens=20),
        )


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up global state after each test."""
    yield
    # Reset global instances
    set_config(None)
    set_transport(None)
    set_registry(None)
    ambertrace.disable()


@respx.mock
def test_init_creates_all_components():
    """Test that init() creates config, transport, and registry."""
    # Mock backend
    respx.post("https://api.ambertrace.dev/api/traces/ingest").mock(return_value=httpx.Response(201))

    # Initialize
    ambertrace.init(api_key="test_key_1234567890")

    # Verify components are created
    assert ambertrace.is_enabled() is True

    # Cleanup
    ambertrace.disable()


@respx.mock
def test_init_with_disabled_flag():
    """Test that init() with enabled=False doesn't start tracing."""
    ambertrace.init(api_key="test_key", enabled=False)

    # Should not be enabled
    assert ambertrace.is_enabled() is False


@respx.mock
def test_enable_disable_cycle():
    """Test enabling and disabling tracing."""
    respx.post("https://api.ambertrace.dev/api/traces/ingest").mock(return_value=httpx.Response(201))

    # Initialize
    ambertrace.init(api_key="test_key_1234567890")
    assert ambertrace.is_enabled() is True

    # Disable
    ambertrace.disable()
    assert ambertrace.is_enabled() is False

    # Re-enable
    ambertrace.enable()
    assert ambertrace.is_enabled() is True

    # Cleanup
    ambertrace.disable()


@respx.mock
def test_flush_sends_pending_traces():
    """Test that flush() waits for traces to be sent."""
    route = respx.post("https://api.ambertrace.dev/api/traces/ingest").mock(
        return_value=httpx.Response(201)
    )

    ambertrace.init(api_key="test_key_1234567890")

    # Simulate sending a trace manually
    from ambertrace.transport import get_transport

    transport = get_transport()
    if transport:
        transport.send_trace(
            {
                "trace_id": "test-123",
                "timestamp": "2024-01-01T00:00:00Z",
                "provider": "openai",
                "method": "chat.completions.create",
                "duration_ms": 100.0,
                "request": {"model": "gpt-4", "messages": [], "parameters": {}},
                "response": None,
                "error": None,
                "sdk_version": "ambertrace-python/0.1.0",
            }
        )

    # Flush
    ambertrace.flush(timeout=2.0)

    # Verify trace was sent
    assert route.called

    ambertrace.disable()


@pytest.mark.asyncio
@respx.mock
async def test_flush_async_sends_pending_traces():
    """Test that flush_async() waits for async traces."""
    route = respx.post("https://api.ambertrace.dev/api/traces/ingest").mock(
        return_value=httpx.Response(201)
    )

    ambertrace.init(api_key="test_key_1234567890")

    # Send async trace
    from ambertrace.transport import get_transport

    transport = get_transport()
    if transport:
        transport.send_trace_async(
            {
                "trace_id": "async-test-123",
                "timestamp": "2024-01-01T00:00:00Z",
                "provider": "openai",
                "method": "chat.completions.create",
                "duration_ms": 100.0,
                "request": {"model": "gpt-4", "messages": [], "parameters": {}},
                "response": None,
                "error": None,
                "sdk_version": "ambertrace-python/0.1.0",
            }
        )

    # Async flush
    await ambertrace.flush_async(timeout=2.0)

    # Verify trace was sent
    assert route.called

    ambertrace.disable()


def test_init_without_api_key_fails_silently():
    """Test that init() without API key fails silently (doesn't crash user code)."""
    import os

    # Ensure env var is not set
    old_key = os.environ.get("AMBERTRACE_API_KEY")
    if "AMBERTRACE_API_KEY" in os.environ:
        del os.environ["AMBERTRACE_API_KEY"]

    try:
        # The SDK catches errors internally to not break user code
        # So this should not raise, but tracing should be disabled
        ambertrace.init()

        # Tracing should not be enabled since no API key
        assert ambertrace.is_enabled() is False
    finally:
        # Restore env var
        if old_key:
            os.environ["AMBERTRACE_API_KEY"] = old_key


@respx.mock
def test_init_with_custom_config():
    """Test init() with custom configuration."""
    respx.post("https://custom.backend.io/api/traces/ingest").mock(return_value=httpx.Response(201))

    ambertrace.init(
        api_key="custom_key",
        base_url="https://custom.backend.io",
        environment="staging",
        debug=True,
        timeout=10.0,
    )

    from ambertrace.config import get_config

    config = get_config()
    assert config is not None
    assert config.api_key == "custom_key"
    assert config.base_url == "https://custom.backend.io"
    assert config.environment == "staging"
    assert config.debug is True
    assert config.timeout == 10.0

    ambertrace.disable()


def test_enable_without_init_warns():
    """Test that enable() without init() is safe but doesn't start tracing."""
    # Should not raise
    ambertrace.enable()

    # But tracing won't work without config
    assert ambertrace.is_enabled() is False


def test_disable_without_init_is_safe():
    """Test that disable() without init() doesn't raise."""
    # Should not raise
    ambertrace.disable()


def test_flush_without_init_is_safe():
    """Test that flush() without init() doesn't raise."""
    # Should not raise
    ambertrace.flush()


@pytest.mark.asyncio
async def test_flush_async_without_init_is_safe():
    """Test that flush_async() without init() doesn't raise."""
    # Should not raise
    await ambertrace.flush_async()


@respx.mock
def test_is_enabled_after_init():
    """Test is_enabled() returns correct state."""
    respx.post("https://api.ambertrace.dev/api/traces/ingest").mock(return_value=httpx.Response(201))

    # Initially not enabled
    assert ambertrace.is_enabled() is False

    # After init
    ambertrace.init(api_key="test_key")
    assert ambertrace.is_enabled() is True

    # After disable
    ambertrace.disable()
    assert ambertrace.is_enabled() is False


@respx.mock
def test_multiple_init_calls():
    """Test that calling init() multiple times is safe."""
    respx.post("https://api.ambertrace.dev/api/traces/ingest").mock(return_value=httpx.Response(201))

    ambertrace.init(api_key="test_key_1")
    first_enabled = ambertrace.is_enabled()

    # Call init again
    ambertrace.init(api_key="test_key_2")
    second_enabled = ambertrace.is_enabled()

    # Both should be enabled
    assert first_enabled is True
    assert second_enabled is True

    ambertrace.disable()


@respx.mock
def test_backend_errors_dont_break_user_code():
    """Test that backend errors are handled silently."""
    # Mock backend returning errors
    respx.post("https://api.ambertrace.dev/api/traces/ingest").mock(return_value=httpx.Response(500))

    ambertrace.init(api_key="test_key")

    # Send trace
    from ambertrace.transport import get_transport

    transport = get_transport()
    if transport:
        # Should not raise even though backend returns 500
        transport.send_trace(
            {
                "trace_id": "error-test",
                "timestamp": "2024-01-01T00:00:00Z",
                "provider": "openai",
                "method": "chat.completions.create",
                "duration_ms": 100.0,
                "request": {"model": "gpt-4", "messages": [], "parameters": {}},
                "response": None,
                "error": None,
                "sdk_version": "ambertrace-python/0.1.0",
            }
        )

        # Flush should also not raise
        transport.flush(timeout=2.0)

    ambertrace.disable()


@respx.mock
def test_network_timeout_handled_gracefully():
    """Test that network timeouts don't crash."""

    def timeout_handler(request):
        raise httpx.TimeoutException("Timeout")

    respx.post("https://api.ambertrace.dev/api/traces/ingest").mock(side_effect=timeout_handler)

    ambertrace.init(api_key="test_key", timeout=1.0)

    from ambertrace.transport import get_transport

    transport = get_transport()
    if transport:
        # Should not raise
        transport.send_trace(
            {
                "trace_id": "timeout-test",
                "timestamp": "2024-01-01T00:00:00Z",
                "provider": "openai",
                "method": "chat.completions.create",
                "duration_ms": 100.0,
                "request": {"model": "gpt-4", "messages": [], "parameters": {}},
                "response": None,
                "error": None,
                "sdk_version": "ambertrace-python/0.1.0",
            }
        )

        transport.flush(timeout=2.0)

    ambertrace.disable()


def test_version_is_exported():
    """Test that __version__ is exported from package."""
    assert hasattr(ambertrace, "__version__")
    assert isinstance(ambertrace.__version__, str)
    assert len(ambertrace.__version__) > 0

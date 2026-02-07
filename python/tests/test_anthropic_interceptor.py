"""Tests for the Anthropic interceptor module."""

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

from ambertrace.providers.anthropic.interceptor import AnthropicInterceptor
from ambertrace.providers.anthropic.collector import AnthropicCollector
from ambertrace.transport import Transport, set_transport


class MockAnthropicResponse:
    """Mock Anthropic response object."""

    def __init__(self, content="Hello!", model="claude-3"):
        self.id = "msg-123"
        self.model = model
        self.content = [Mock(type="text", text=content)]
        self.stop_reason = "end_turn"
        self.usage = Mock(input_tokens=10, output_tokens=5)


class TestAnthropicInterceptor:
    """Test cases for AnthropicInterceptor class."""

    @pytest.fixture
    def interceptor(self):
        """Create a fresh interceptor instance."""
        return AnthropicInterceptor()

    @pytest.fixture
    def mock_transport(self):
        """Create a mock transport."""
        transport = Mock(spec=Transport)
        set_transport(transport)
        yield transport
        set_transport(None)

    def test_interceptor_initialization(self, interceptor):
        """Test interceptor initializes correctly."""
        assert interceptor._original_sync_create is None
        assert interceptor._original_async_create is None
        assert interceptor._is_patched is False
        assert isinstance(interceptor._collector, AnthropicCollector)

    def test_is_patched_initially_false(self, interceptor):
        """Test is_patched returns False initially."""
        assert interceptor.is_patched() is False

    def test_get_provider_name(self, interceptor):
        """Test provider name is correct."""
        assert interceptor.get_provider_name() == "anthropic"

    def test_patch_applies_successfully(self, interceptor):
        """Test patching Anthropic methods."""
        # Setup mock Anthropic structure
        mock_anthropic = MagicMock()
        mock_messages = MagicMock()
        mock_messages.create = MagicMock()

        mock_async_messages = MagicMock()
        mock_async_messages.create = MagicMock()

        mock_anthropic.Anthropic = MagicMock()
        mock_anthropic.AsyncAnthropic = MagicMock()
        mock_anthropic.resources.Messages = mock_messages
        mock_anthropic.resources.AsyncMessages = mock_async_messages

        # Temporarily replace anthropic in sys.modules
        original_anthropic = sys.modules.get("anthropic")
        sys.modules["anthropic"] = mock_anthropic

        try:
            # Apply patches
            interceptor.patch()

            # Verify state
            assert interceptor.is_patched() is True
            assert interceptor._original_sync_create is not None
            assert interceptor._original_async_create is not None
        finally:
            # Restore original
            if original_anthropic is not None:
                sys.modules["anthropic"] = original_anthropic
            elif "anthropic" in sys.modules:
                del sys.modules["anthropic"]

    def test_unpatch_restores_original(self, interceptor):
        """Test unpatching restores original methods."""
        # Setup mocks
        mock_anthropic = MagicMock()
        original_sync = MagicMock()
        original_async = MagicMock()

        mock_messages = MagicMock()
        mock_messages.create = original_sync

        mock_async_messages = MagicMock()
        mock_async_messages.create = original_async

        mock_anthropic.Anthropic = MagicMock()
        mock_anthropic.AsyncAnthropic = MagicMock()
        mock_anthropic.resources.Messages = mock_messages
        mock_anthropic.resources.AsyncMessages = mock_async_messages

        # Temporarily replace anthropic in sys.modules
        original_anthropic = sys.modules.get("anthropic")
        sys.modules["anthropic"] = mock_anthropic

        try:
            # Patch and unpatch
            interceptor.patch()
            interceptor.unpatch()

            # Verify restored
            assert interceptor.is_patched() is False
            assert interceptor._original_sync_create is None
            assert interceptor._original_async_create is None
        finally:
            # Restore original
            if original_anthropic is not None:
                sys.modules["anthropic"] = original_anthropic
            elif "anthropic" in sys.modules:
                del sys.modules["anthropic"]

    def test_wrap_sync_create_preserves_response(self, interceptor, mock_transport):
        """Test sync wrapper preserves original response."""
        # Create mock original method
        mock_response = MockAnthropicResponse()
        original_method = Mock(return_value=mock_response)

        # Create wrapper
        wrapped = interceptor._wrap_sync_create(original_method)

        # Call wrapped method
        mock_self = MagicMock()
        result = wrapped(
            mock_self,
            model="claude-3",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1024
        )

        # Verify response is unchanged
        assert result == mock_response
        original_method.assert_called_once()

    def test_wrap_sync_create_reraises_exception(self, interceptor, mock_transport):
        """Test sync wrapper re-raises exceptions."""
        # Create mock that raises
        original_method = Mock(side_effect=ValueError("API error"))

        # Create wrapper
        wrapped = interceptor._wrap_sync_create(original_method)

        # Call and verify exception is raised
        mock_self = MagicMock()
        with pytest.raises(ValueError, match="API error"):
            wrapped(
                mock_self,
                model="claude-3",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1024
            )

    def test_wrap_sync_create_sends_trace(self, interceptor, mock_transport):
        """Test sync wrapper sends trace to transport."""
        # Setup
        mock_response = MockAnthropicResponse()
        original_method = Mock(return_value=mock_response)
        wrapped = interceptor._wrap_sync_create(original_method)

        # Call wrapped method
        mock_self = MagicMock()
        with patch.object(interceptor._collector, "collect_trace") as mock_collect:
            mock_collect.return_value = {"trace_id": "123", "timestamp": "2024-01-01T00:00:00Z"}

            wrapped(
                mock_self,
                model="claude-3",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1024
            )

            # Verify trace was collected
            mock_collect.assert_called_once()
            call_kwargs = mock_collect.call_args[1]
            assert "trace_id" in call_kwargs
            assert "start_time" in call_kwargs
            assert call_kwargs["response"] == mock_response
            assert call_kwargs["error"] is None

            # Verify trace was sent
            mock_transport.send_trace.assert_called_once()

    def test_wrap_sync_create_sends_error_trace(self, interceptor, mock_transport):
        """Test sync wrapper sends trace on error."""
        # Setup
        error = ValueError("API error")
        original_method = Mock(side_effect=error)
        wrapped = interceptor._wrap_sync_create(original_method)

        # Call and expect exception
        mock_self = MagicMock()
        with patch.object(interceptor._collector, "collect_trace") as mock_collect:
            mock_collect.return_value = {"trace_id": "123", "error": {"type": "ValueError"}}

            with pytest.raises(ValueError):
                wrapped(
                    mock_self,
                    model="claude-3",
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=1024
                )

            # Verify error trace was collected
            mock_collect.assert_called_once()
            call_kwargs = mock_collect.call_args[1]
            assert call_kwargs["response"] is None
            assert call_kwargs["error"] == error

            # Verify trace was sent
            mock_transport.send_trace.assert_called_once()

    @pytest.mark.asyncio
    async def test_wrap_async_create_preserves_response(self, interceptor, mock_transport):
        """Test async wrapper preserves original response."""
        # Create mock async method
        mock_response = MockAnthropicResponse()

        async def original_method(self_instance, *args, **kwargs):
            return mock_response

        # Create wrapper
        wrapped = interceptor._wrap_async_create(original_method)

        # Call wrapped method
        mock_self = MagicMock()
        result = await wrapped(
            mock_self,
            model="claude-3",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1024
        )

        # Verify response is unchanged
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_wrap_async_create_reraises_exception(self, interceptor, mock_transport):
        """Test async wrapper re-raises exceptions."""

        # Create mock that raises
        async def original_method(self_instance, *args, **kwargs):
            raise ValueError("API error")

        # Create wrapper
        wrapped = interceptor._wrap_async_create(original_method)

        # Call and verify exception is raised
        mock_self = MagicMock()
        with pytest.raises(ValueError, match="API error"):
            await wrapped(
                mock_self,
                model="claude-3",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1024
            )

    @pytest.mark.asyncio
    async def test_wrap_async_create_sends_trace(self, interceptor, mock_transport):
        """Test async wrapper sends trace to transport."""
        # Setup
        mock_response = MockAnthropicResponse()

        async def original_method(self_instance, *args, **kwargs):
            return mock_response

        wrapped = interceptor._wrap_async_create(original_method)

        # Call wrapped method
        mock_self = MagicMock()
        with patch.object(interceptor._collector, "collect_trace") as mock_collect:
            mock_collect.return_value = {"trace_id": "123", "timestamp": "2024-01-01T00:00:00Z"}

            await wrapped(
                mock_self,
                model="claude-3",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1024
            )

            # Verify trace was collected
            mock_collect.assert_called_once()

            # Verify async send was called
            mock_transport.send_trace_async.assert_called_once()

    def test_wrap_sync_never_raises_on_trace_error(self, interceptor, mock_transport):
        """Test wrapper doesn't raise if trace collection fails."""
        # Setup - collector raises but original method succeeds
        mock_response = MockAnthropicResponse()
        original_method = Mock(return_value=mock_response)
        wrapped = interceptor._wrap_sync_create(original_method)

        mock_self = MagicMock()
        with patch.object(interceptor._collector, "collect_trace", side_effect=Exception("Trace error")):
            # Should not raise - trace errors are caught
            result = wrapped(
                mock_self,
                model="claude-3",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1024
            )

            # Original response still returned
            assert result == mock_response

    @pytest.mark.asyncio
    async def test_wrap_async_never_raises_on_trace_error(self, interceptor, mock_transport):
        """Test async wrapper doesn't raise if trace collection fails."""
        # Setup - collector raises but original method succeeds
        mock_response = MockAnthropicResponse()

        async def original_method(self_instance, *args, **kwargs):
            return mock_response

        wrapped = interceptor._wrap_async_create(original_method)

        mock_self = MagicMock()
        with patch.object(interceptor._collector, "collect_trace", side_effect=Exception("Trace error")):
            # Should not raise - trace errors are caught
            result = await wrapped(
                mock_self,
                model="claude-3",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1024
            )

            # Original response still returned
            assert result == mock_response

    def test_patch_handles_missing_anthropic(self, interceptor):
        """Test patch handles case when Anthropic SDK structure is different."""
        # Setup - Anthropic exists but doesn't have expected structure
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic = MagicMock()
        mock_anthropic.AsyncAnthropic = MagicMock()
        del mock_anthropic.resources  # Remove resources

        # Temporarily replace anthropic in sys.modules
        original_anthropic = sys.modules.get("anthropic")
        sys.modules["anthropic"] = mock_anthropic

        try:
            # Should not raise
            interceptor.patch()

            # State should reflect partial patch
            assert interceptor._is_patched is True  # Patching completed (even if partial)
        finally:
            # Restore original
            if original_anthropic is not None:
                sys.modules["anthropic"] = original_anthropic
            elif "anthropic" in sys.modules:
                del sys.modules["anthropic"]

    def test_patch_when_already_patched(self, interceptor):
        """Test that patching twice is a no-op."""
        # Setup mock Anthropic
        mock_anthropic = MagicMock()
        mock_messages = MagicMock()
        mock_messages.create = MagicMock()
        mock_anthropic.Anthropic = MagicMock()
        mock_anthropic.AsyncAnthropic = MagicMock()
        mock_anthropic.resources.Messages = mock_messages
        mock_anthropic.resources.AsyncMessages = MagicMock()
        mock_anthropic.resources.AsyncMessages.create = MagicMock()

        original_anthropic = sys.modules.get("anthropic")
        sys.modules["anthropic"] = mock_anthropic

        try:
            # Patch once
            interceptor.patch()
            first_sync = interceptor._original_sync_create

            # Patch again
            interceptor.patch()
            second_sync = interceptor._original_sync_create

            # Should be the same reference (no double patching)
            assert first_sync is second_sync
        finally:
            if original_anthropic is not None:
                sys.modules["anthropic"] = original_anthropic
            elif "anthropic" in sys.modules:
                del sys.modules["anthropic"]

    def test_unpatch_when_not_patched(self, interceptor):
        """Test that unpatching when not patched is a no-op."""
        # Should not raise
        interceptor.unpatch()

        # State should be unchanged
        assert interceptor._is_patched is False
        assert interceptor._original_sync_create is None
        assert interceptor._original_async_create is None

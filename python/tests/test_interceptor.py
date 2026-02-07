"""Tests for the OpenAI interceptor module."""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from ambertrace.providers.openai.interceptor import OpenAIInterceptor
from ambertrace.providers.openai.collector import OpenAICollector
from ambertrace.transport import Transport, set_transport


class MockOpenAIResponse:
    """Mock OpenAI response object."""

    def __init__(self, content="Hello!", model="gpt-4"):
        self.id = "chatcmpl-123"
        self.model = model
        self.choices = [
            Mock(
                index=0,
                message=Mock(role="assistant", content=content),
                finish_reason="stop",
            )
        ]
        self.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)


class TestOpenAIInterceptor:
    """Test cases for OpenAIInterceptor class."""

    @pytest.fixture
    def interceptor(self):
        """Create a fresh interceptor instance."""
        return OpenAIInterceptor()

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
        assert isinstance(interceptor._collector, OpenAICollector)

    def test_is_patched_initially_false(self, interceptor):
        """Test is_patched returns False initially."""
        assert interceptor.is_patched() is False

    def test_get_provider_name(self, interceptor):
        """Test provider name is correct."""
        assert interceptor.get_provider_name() == "openai"

    def test_patch_applies_successfully(self, interceptor):
        """Test patching OpenAI methods."""
        import sys

        # Setup mock OpenAI structure
        mock_openai = MagicMock()
        mock_completions = MagicMock()
        mock_completions.create = MagicMock()

        mock_async_completions = MagicMock()
        mock_async_completions.create = MagicMock()

        mock_openai.OpenAI = MagicMock()
        mock_openai.AsyncOpenAI = MagicMock()
        mock_openai.resources.chat.Completions = mock_completions
        mock_openai.resources.chat.AsyncCompletions = mock_async_completions

        # Temporarily replace openai in sys.modules
        original_openai = sys.modules.get("openai")
        sys.modules["openai"] = mock_openai

        try:
            # Apply patches
            interceptor.patch()

            # Verify state
            assert interceptor.is_patched() is True
            assert interceptor._original_sync_create is not None
            assert interceptor._original_async_create is not None
        finally:
            # Restore original
            if original_openai is not None:
                sys.modules["openai"] = original_openai
            elif "openai" in sys.modules:
                del sys.modules["openai"]

    def test_unpatch_restores_original(self, interceptor):
        """Test unpatching restores original methods."""
        import sys

        # Setup mocks
        mock_openai = MagicMock()
        original_sync = MagicMock()
        original_async = MagicMock()

        mock_completions = MagicMock()
        mock_completions.create = original_sync

        mock_async_completions = MagicMock()
        mock_async_completions.create = original_async

        mock_openai.OpenAI = MagicMock()
        mock_openai.AsyncOpenAI = MagicMock()
        mock_openai.resources.chat.Completions = mock_completions
        mock_openai.resources.chat.AsyncCompletions = mock_async_completions

        # Temporarily replace openai in sys.modules
        original_openai = sys.modules.get("openai")
        sys.modules["openai"] = mock_openai

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
            if original_openai is not None:
                sys.modules["openai"] = original_openai
            elif "openai" in sys.modules:
                del sys.modules["openai"]

    def test_wrap_sync_create_preserves_response(self, interceptor, mock_transport):
        """Test sync wrapper preserves original response."""
        # Create mock original method
        mock_response = MockOpenAIResponse()
        original_method = Mock(return_value=mock_response)

        # Create wrapper
        wrapped = interceptor._wrap_sync_create(original_method)

        # Call wrapped method
        mock_self = MagicMock()
        result = wrapped(mock_self, model="gpt-4", messages=[{"role": "user", "content": "Hi"}])

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
            wrapped(mock_self, model="gpt-4", messages=[{"role": "user", "content": "Hi"}])

    def test_wrap_sync_create_sends_trace(self, interceptor, mock_transport):
        """Test sync wrapper sends trace to transport."""
        # Setup
        mock_response = MockOpenAIResponse()
        original_method = Mock(return_value=mock_response)
        wrapped = interceptor._wrap_sync_create(original_method)

        # Call wrapped method
        mock_self = MagicMock()
        with patch.object(interceptor._collector, "collect_trace") as mock_collect:
            mock_collect.return_value = {"trace_id": "123", "timestamp": "2024-01-01T00:00:00Z"}

            wrapped(
                mock_self, model="gpt-4", messages=[{"role": "user", "content": "Hi"}]
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
                    mock_self, model="gpt-4", messages=[{"role": "user", "content": "Hi"}]
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
        mock_response = MockOpenAIResponse()

        async def original_method(self_instance, *args, **kwargs):
            return mock_response

        # Create wrapper
        wrapped = interceptor._wrap_async_create(original_method)

        # Call wrapped method
        mock_self = MagicMock()
        result = await wrapped(
            mock_self, model="gpt-4", messages=[{"role": "user", "content": "Hi"}]
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
                mock_self, model="gpt-4", messages=[{"role": "user", "content": "Hi"}]
            )

    @pytest.mark.asyncio
    async def test_wrap_async_create_sends_trace(self, interceptor, mock_transport):
        """Test async wrapper sends trace to transport."""
        # Setup
        mock_response = MockOpenAIResponse()

        async def original_method(self_instance, *args, **kwargs):
            return mock_response

        wrapped = interceptor._wrap_async_create(original_method)

        # Call wrapped method
        mock_self = MagicMock()
        with patch.object(interceptor._collector, "collect_trace") as mock_collect:
            mock_collect.return_value = {"trace_id": "123", "timestamp": "2024-01-01T00:00:00Z"}

            await wrapped(
                mock_self, model="gpt-4", messages=[{"role": "user", "content": "Hi"}]
            )

            # Verify trace was collected
            mock_collect.assert_called_once()

            # Verify async send was called
            mock_transport.send_trace_async.assert_called_once()

    def test_wrap_sync_never_raises_on_trace_error(self, interceptor, mock_transport):
        """Test wrapper doesn't raise if trace collection fails."""
        # Setup - collector raises but original method succeeds
        mock_response = MockOpenAIResponse()
        original_method = Mock(return_value=mock_response)
        wrapped = interceptor._wrap_sync_create(original_method)

        mock_self = MagicMock()
        with patch.object(interceptor._collector, "collect_trace", side_effect=Exception("Trace error")):
            # Should not raise - trace errors are caught
            result = wrapped(
                mock_self, model="gpt-4", messages=[{"role": "user", "content": "Hi"}]
            )

            # Original response still returned
            assert result == mock_response

    @pytest.mark.asyncio
    async def test_wrap_async_never_raises_on_trace_error(self, interceptor, mock_transport):
        """Test async wrapper doesn't raise if trace collection fails."""
        # Setup - collector raises but original method succeeds
        mock_response = MockOpenAIResponse()

        async def original_method(self_instance, *args, **kwargs):
            return mock_response

        wrapped = interceptor._wrap_async_create(original_method)

        mock_self = MagicMock()
        with patch.object(interceptor._collector, "collect_trace", side_effect=Exception("Trace error")):
            # Should not raise - trace errors are caught
            result = await wrapped(
                mock_self, model="gpt-4", messages=[{"role": "user", "content": "Hi"}]
            )

            # Original response still returned
            assert result == mock_response

    def test_patch_handles_missing_openai(self, interceptor):
        """Test patch handles case when OpenAI SDK structure is different."""
        import sys

        # Setup - OpenAI exists but doesn't have expected structure
        mock_openai = MagicMock()
        mock_openai.OpenAI = MagicMock()
        mock_openai.AsyncOpenAI = MagicMock()
        del mock_openai.resources  # Remove resources

        # Temporarily replace openai in sys.modules
        original_openai = sys.modules.get("openai")
        sys.modules["openai"] = mock_openai

        try:
            # Should not raise
            interceptor.patch()

            # State should reflect partial patch
            assert interceptor._is_patched is True  # Patching completed (even if partial)
        finally:
            # Restore original
            if original_openai is not None:
                sys.modules["openai"] = original_openai
            elif "openai" in sys.modules:
                del sys.modules["openai"]

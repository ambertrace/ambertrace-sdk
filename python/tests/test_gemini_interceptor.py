"""Tests for the Gemini interceptor module."""

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

from ambertrace.providers.gemini.interceptor import GeminiInterceptor
from ambertrace.providers.gemini.collector import GeminiCollector
from ambertrace.transport import Transport, set_transport


class MockGeminiResponse:
    """Mock Gemini response object."""

    def __init__(self, text="Hello! How can I help?"):
        self.response_id = "gemini-resp-123"
        self.model = "gemini-pro"
        self.candidates = [
            Mock(
                content=Mock(parts=[Mock(text=text)]),
                finish_reason="STOP",
            )
        ]
        self.usage_metadata = Mock(
            prompt_token_count=15,
            candidates_token_count=8,
            total_token_count=23,
        )
        self.text = text


class TestGeminiInterceptor:
    """Test cases for GeminiInterceptor class."""

    @pytest.fixture
    def interceptor(self):
        """Create a fresh interceptor instance."""
        return GeminiInterceptor()

    @pytest.fixture
    def mock_transport(self):
        """Create a mock transport."""
        transport = Mock(spec=Transport)
        set_transport(transport)
        yield transport
        set_transport(None)

    def test_interceptor_initialization(self, interceptor):
        """Test interceptor initializes correctly."""
        assert interceptor._original_genai_sync is None
        assert interceptor._original_genai_async is None
        assert interceptor._genai_patched is False
        assert interceptor._original_genai2_sync is None
        assert interceptor._original_genai2_async is None
        assert interceptor._genai2_patched is False
        assert isinstance(interceptor._collector, GeminiCollector)

    def test_is_patched_initially_false(self, interceptor):
        """Test is_patched returns False initially."""
        assert interceptor.is_patched() is False

    def test_get_provider_name(self, interceptor):
        """Test provider name is correct."""
        assert interceptor.get_provider_name() == "gemini"

    def test_patch_original_sdk(self, interceptor):
        """Test patching original google-generativeai SDK."""
        # Setup mock google.generativeai
        mock_genai = MagicMock()
        mock_model_class = MagicMock()
        mock_model_class.generate_content = MagicMock()
        mock_model_class.generate_content_async = MagicMock()
        mock_genai.GenerativeModel = mock_model_class

        # Setup module hierarchy
        mock_google = MagicMock()
        mock_google.generativeai = mock_genai

        original_google = sys.modules.get("google")
        original_genai = sys.modules.get("google.generativeai")
        sys.modules["google"] = mock_google
        sys.modules["google.generativeai"] = mock_genai

        try:
            interceptor.patch()

            assert interceptor._genai_patched is True
            assert interceptor.is_patched() is True
            assert interceptor._original_genai_sync is not None
            assert interceptor._original_genai_async is not None
        finally:
            if original_google is not None:
                sys.modules["google"] = original_google
            elif "google" in sys.modules:
                del sys.modules["google"]
            if original_genai is not None:
                sys.modules["google.generativeai"] = original_genai
            elif "google.generativeai" in sys.modules:
                del sys.modules["google.generativeai"]

    def test_unpatch_restores_original(self, interceptor):
        """Test unpatching restores original methods."""
        # Setup mock
        mock_genai = MagicMock()
        original_sync = MagicMock()
        original_async = MagicMock()
        mock_model_class = MagicMock()
        mock_model_class.generate_content = original_sync
        mock_model_class.generate_content_async = original_async
        mock_genai.GenerativeModel = mock_model_class

        mock_google = MagicMock()
        mock_google.generativeai = mock_genai

        original_google = sys.modules.get("google")
        original_genai_mod = sys.modules.get("google.generativeai")
        sys.modules["google"] = mock_google
        sys.modules["google.generativeai"] = mock_genai

        try:
            interceptor.patch()
            interceptor.unpatch()

            assert interceptor.is_patched() is False
            assert interceptor._original_genai_sync is None
            assert interceptor._original_genai_async is None
            assert interceptor._genai_patched is False
        finally:
            if original_google is not None:
                sys.modules["google"] = original_google
            elif "google" in sys.modules:
                del sys.modules["google"]
            if original_genai_mod is not None:
                sys.modules["google.generativeai"] = original_genai_mod
            elif "google.generativeai" in sys.modules:
                del sys.modules["google.generativeai"]

    def test_wrap_genai_sync_preserves_response(self, interceptor, mock_transport):
        """Test sync wrapper preserves original response."""
        mock_response = MockGeminiResponse()
        original_method = Mock(return_value=mock_response)

        wrapped = interceptor._wrap_genai_sync(original_method)

        # Create mock instance with model_name
        mock_self = MagicMock()
        mock_self.model_name = "gemini-pro"

        result = wrapped(mock_self, "Hello!")

        assert result == mock_response
        original_method.assert_called_once()

    def test_wrap_genai_sync_reraises_exception(self, interceptor, mock_transport):
        """Test sync wrapper re-raises exceptions."""
        original_method = Mock(side_effect=ValueError("API error"))

        wrapped = interceptor._wrap_genai_sync(original_method)

        mock_self = MagicMock()
        mock_self.model_name = "gemini-pro"

        with pytest.raises(ValueError, match="API error"):
            wrapped(mock_self, "Hello!")

    def test_wrap_genai_sync_sends_trace(self, interceptor, mock_transport):
        """Test sync wrapper sends trace to transport."""
        mock_response = MockGeminiResponse()
        original_method = Mock(return_value=mock_response)
        wrapped = interceptor._wrap_genai_sync(original_method)

        mock_self = MagicMock()
        mock_self.model_name = "gemini-pro"

        with patch.object(interceptor._collector, "collect_trace") as mock_collect:
            mock_collect.return_value = {"trace_id": "123"}

            wrapped(mock_self, "Hello!")

            mock_collect.assert_called_once()
            call_kwargs = mock_collect.call_args[1]
            assert "trace_id" in call_kwargs
            assert call_kwargs["response"] == mock_response
            assert call_kwargs["error"] is None
            assert call_kwargs["request_kwargs"]["_ambertrace_model"] == "gemini-pro"
            assert call_kwargs["request_kwargs"]["contents"] == "Hello!"

            mock_transport.send_trace.assert_called_once()

    def test_wrap_genai_sync_sends_error_trace(self, interceptor, mock_transport):
        """Test sync wrapper sends trace on error."""
        error = ValueError("API error")
        original_method = Mock(side_effect=error)
        wrapped = interceptor._wrap_genai_sync(original_method)

        mock_self = MagicMock()
        mock_self.model_name = "gemini-pro"

        with patch.object(interceptor._collector, "collect_trace") as mock_collect:
            mock_collect.return_value = {"trace_id": "123", "error": {"type": "ValueError"}}

            with pytest.raises(ValueError):
                wrapped(mock_self, "Hello!")

            mock_collect.assert_called_once()
            call_kwargs = mock_collect.call_args[1]
            assert call_kwargs["response"] is None
            assert call_kwargs["error"] == error

            mock_transport.send_trace.assert_called_once()

    @pytest.mark.asyncio
    async def test_wrap_genai_async_preserves_response(self, interceptor, mock_transport):
        """Test async wrapper preserves original response."""
        mock_response = MockGeminiResponse()

        async def original_method(self_instance, *args, **kwargs):
            return mock_response

        wrapped = interceptor._wrap_genai_async(original_method)

        mock_self = MagicMock()
        mock_self.model_name = "gemini-pro"

        result = await wrapped(mock_self, "Hello!")

        assert result == mock_response

    @pytest.mark.asyncio
    async def test_wrap_genai_async_reraises_exception(self, interceptor, mock_transport):
        """Test async wrapper re-raises exceptions."""

        async def original_method(self_instance, *args, **kwargs):
            raise ValueError("API error")

        wrapped = interceptor._wrap_genai_async(original_method)

        mock_self = MagicMock()
        mock_self.model_name = "gemini-pro"

        with pytest.raises(ValueError, match="API error"):
            await wrapped(mock_self, "Hello!")

    @pytest.mark.asyncio
    async def test_wrap_genai_async_sends_trace(self, interceptor, mock_transport):
        """Test async wrapper sends trace to transport."""
        mock_response = MockGeminiResponse()

        async def original_method(self_instance, *args, **kwargs):
            return mock_response

        wrapped = interceptor._wrap_genai_async(original_method)

        mock_self = MagicMock()
        mock_self.model_name = "gemini-pro"

        with patch.object(interceptor._collector, "collect_trace") as mock_collect:
            mock_collect.return_value = {"trace_id": "123"}

            await wrapped(mock_self, "Hello!")

            mock_collect.assert_called_once()
            mock_transport.send_trace_async.assert_called_once()

    def test_wrap_genai_sync_never_raises_on_trace_error(self, interceptor, mock_transport):
        """Test wrapper doesn't raise if trace collection fails."""
        mock_response = MockGeminiResponse()
        original_method = Mock(return_value=mock_response)
        wrapped = interceptor._wrap_genai_sync(original_method)

        mock_self = MagicMock()
        mock_self.model_name = "gemini-pro"

        with patch.object(interceptor._collector, "collect_trace", side_effect=Exception("Trace error")):
            result = wrapped(mock_self, "Hello!")
            assert result == mock_response

    def test_wrap_extracts_model_from_instance(self, interceptor, mock_transport):
        """Test that model name is extracted from GenerativeModel instance."""
        mock_response = MockGeminiResponse()
        original_method = Mock(return_value=mock_response)
        wrapped = interceptor._wrap_genai_sync(original_method)

        mock_self = MagicMock()
        mock_self.model_name = "models/gemini-1.5-pro"

        with patch.object(interceptor._collector, "collect_trace") as mock_collect:
            mock_collect.return_value = {"trace_id": "123"}

            wrapped(mock_self, "Hello!")

            call_kwargs = mock_collect.call_args[1]
            assert call_kwargs["request_kwargs"]["_ambertrace_model"] == "models/gemini-1.5-pro"

    def test_wrap_captures_contents_from_positional_args(self, interceptor, mock_transport):
        """Test that contents from positional args is captured."""
        mock_response = MockGeminiResponse()
        original_method = Mock(return_value=mock_response)
        wrapped = interceptor._wrap_genai_sync(original_method)

        mock_self = MagicMock()
        mock_self.model_name = "gemini-pro"

        with patch.object(interceptor._collector, "collect_trace") as mock_collect:
            mock_collect.return_value = {"trace_id": "123"}

            # Pass contents as positional arg
            wrapped(mock_self, "Tell me a joke")

            call_kwargs = mock_collect.call_args[1]
            assert call_kwargs["request_kwargs"]["contents"] == "Tell me a joke"

    def test_wrap_genai2_sync_preserves_response(self, interceptor, mock_transport):
        """Test newer SDK sync wrapper preserves response."""
        mock_response = MockGeminiResponse()
        original_method = Mock(return_value=mock_response)

        wrapped = interceptor._wrap_genai2_sync(original_method)

        mock_self = MagicMock()
        result = wrapped(
            mock_self,
            model="gemini-2.0-flash",
            contents="Hello!",
        )

        assert result == mock_response
        original_method.assert_called_once()

    def test_wrap_genai2_sync_sends_trace(self, interceptor, mock_transport):
        """Test newer SDK sync wrapper sends trace."""
        mock_response = MockGeminiResponse()
        original_method = Mock(return_value=mock_response)
        wrapped = interceptor._wrap_genai2_sync(original_method)

        mock_self = MagicMock()

        with patch.object(interceptor._collector, "collect_trace") as mock_collect:
            mock_collect.return_value = {"trace_id": "123"}

            wrapped(mock_self, model="gemini-2.0-flash", contents="Hello!")

            mock_collect.assert_called_once()
            call_kwargs = mock_collect.call_args[1]
            assert call_kwargs["request_kwargs"]["model"] == "gemini-2.0-flash"
            assert call_kwargs["request_kwargs"]["contents"] == "Hello!"

            mock_transport.send_trace.assert_called_once()

    @pytest.mark.asyncio
    async def test_wrap_genai2_async_preserves_response(self, interceptor, mock_transport):
        """Test newer SDK async wrapper preserves response."""
        mock_response = MockGeminiResponse()

        async def original_method(self_instance, *args, **kwargs):
            return mock_response

        wrapped = interceptor._wrap_genai2_async(original_method)

        mock_self = MagicMock()
        result = await wrapped(mock_self, model="gemini-2.0-flash", contents="Hello!")

        assert result == mock_response

    def test_patch_idempotent(self, interceptor):
        """Test that calling patch() twice is a no-op."""
        mock_genai = MagicMock()
        mock_model_class = MagicMock()
        mock_model_class.generate_content = MagicMock()
        mock_model_class.generate_content_async = MagicMock()
        mock_genai.GenerativeModel = mock_model_class

        mock_google = MagicMock()
        mock_google.generativeai = mock_genai

        original_google = sys.modules.get("google")
        original_genai_mod = sys.modules.get("google.generativeai")
        sys.modules["google"] = mock_google
        sys.modules["google.generativeai"] = mock_genai

        try:
            interceptor.patch()
            first_sync = interceptor._original_genai_sync

            interceptor.patch()
            second_sync = interceptor._original_genai_sync

            assert first_sync is second_sync
        finally:
            if original_google is not None:
                sys.modules["google"] = original_google
            elif "google" in sys.modules:
                del sys.modules["google"]
            if original_genai_mod is not None:
                sys.modules["google.generativeai"] = original_genai_mod
            elif "google.generativeai" in sys.modules:
                del sys.modules["google.generativeai"]

    def test_unpatch_when_not_patched(self, interceptor):
        """Test that unpatching when not patched is a no-op."""
        interceptor.unpatch()

        assert interceptor.is_patched() is False
        assert interceptor._original_genai_sync is None
        assert interceptor._original_genai_async is None

    def test_is_patched_reflects_any_sdk(self, interceptor):
        """Test is_patched returns True if either SDK is patched."""
        assert interceptor.is_patched() is False

        # Simulate only genai_patched
        interceptor._genai_patched = True
        assert interceptor.is_patched() is True

        interceptor._genai_patched = False
        interceptor._genai2_patched = True
        assert interceptor.is_patched() is True

        interceptor._genai_patched = True
        interceptor._genai2_patched = True
        assert interceptor.is_patched() is True

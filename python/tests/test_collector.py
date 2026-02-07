"""Tests for the OpenAI collector module."""

import time
from unittest.mock import Mock

import pytest

from ambertrace.providers.openai.collector import OpenAICollector
from ambertrace.config import Config, set_config
from ambertrace.models import Choice, ErrorData, Message, RequestData, ResponseData, UsageData


class MockOpenAIResponse:
    """Mock OpenAI response object."""

    def __init__(self):
        self.id = "chatcmpl-abc123"
        self.model = "gpt-4-0613"
        self.choices = [
            Mock(
                index=0,
                message=Mock(role="assistant", content="Hello! How can I help you?"),
                finish_reason="stop",
            )
        ]
        self.usage = Mock(prompt_tokens=20, completion_tokens=10, total_tokens=30)


class TestOpenAICollector:
    """Test cases for OpenAICollector."""

    @pytest.fixture
    def collector(self):
        """Create a collector instance."""
        return OpenAICollector()

    @pytest.fixture
    def config(self):
        """Setup test configuration."""
        config = Config(api_key="test_key", environment="test")
        set_config(config)
        yield config
        set_config(None)

    @pytest.fixture
    def request_kwargs(self):
        """Sample request kwargs."""
        return {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"},
            ],
            "temperature": 0.7,
            "max_tokens": 150,
        }

    @pytest.fixture
    def mock_response(self):
        """Create a mock OpenAI response."""
        return MockOpenAIResponse()

    def test_get_provider_name(self, collector):
        """Test that provider name is correct."""
        assert collector.get_provider_name() == "openai"

    def test_collect_trace_success(self, collector, config, request_kwargs, mock_response):
        """Test collecting a successful trace."""
        trace_id = "test-trace-123"
        start_time = time.time()

        trace_dict = collector.collect_trace(
            trace_id=trace_id,
            start_time=start_time,
            request_kwargs=request_kwargs,
            response=mock_response,
            error=None,
        )

        # Verify trace was collected
        assert trace_dict is not None
        assert trace_dict["trace_id"] == trace_id
        assert trace_dict["provider"] == "openai"
        assert trace_dict["method"] == "chat.completions.create"
        assert "timestamp" in trace_dict
        assert trace_dict["duration_ms"] >= 0
        assert trace_dict["environment"] == "test"
        assert trace_dict["status"] == "success"

        # Verify request data (flattened format)
        assert trace_dict["request_model"] == "gpt-4"
        assert trace_dict["request_data"]["model"] == "gpt-4"
        assert len(trace_dict["request_data"]["messages"]) == 2
        assert trace_dict["request_data"]["messages"][0]["role"] == "system"
        assert trace_dict["request_data"]["messages"][1]["role"] == "user"
        assert trace_dict["request_data"]["parameters"]["temperature"] == 0.7
        assert trace_dict["request_data"]["parameters"]["max_tokens"] == 150

        # Verify response data (flattened format)
        assert trace_dict["response_data"] is not None
        assert trace_dict["response_data"]["id"] == "chatcmpl-abc123"
        assert trace_dict["response_data"]["model"] == "gpt-4-0613"
        assert len(trace_dict["response_data"]["choices"]) == 1
        assert trace_dict["response_data"]["choices"][0]["message"]["role"] == "assistant"
        assert "Hello" in trace_dict["response_data"]["choices"][0]["message"]["content"]
        assert trace_dict["prompt_tokens"] == 20
        assert trace_dict["completion_tokens"] == 10
        assert trace_dict["total_tokens"] == 30

        # Verify error is None
        assert trace_dict["error_data"] is None

    def test_collect_trace_with_error(self, collector, config, request_kwargs):
        """Test collecting a trace when an error occurs."""
        trace_id = "test-trace-error"
        start_time = time.time()
        error = ValueError("Invalid API key")

        trace_dict = collector.collect_trace(
            trace_id=trace_id,
            start_time=start_time,
            request_kwargs=request_kwargs,
            response=None,
            error=error,
        )

        # Verify trace was collected
        assert trace_dict is not None
        assert trace_dict["trace_id"] == trace_id
        assert trace_dict["status"] == "error"

        # Verify request data is present (flattened format)
        assert trace_dict["request_model"] == "gpt-4"
        assert trace_dict["request_data"]["model"] == "gpt-4"

        # Verify response is None
        assert trace_dict["response_data"] is None

        # Verify error data (flattened format)
        assert trace_dict["error_data"] is not None
        assert trace_dict["error_data"]["type"] == "ValueError"
        assert trace_dict["error_data"]["message"] == "Invalid API key"

    def test_collect_trace_with_openai_error_code(self, collector, config, request_kwargs):
        """Test collecting trace with OpenAI error that has a code."""
        trace_id = "test-trace-with-code"
        start_time = time.time()

        # Mock error with code attribute
        error = ValueError("Rate limit exceeded")
        error.code = "rate_limit_exceeded"

        trace_dict = collector.collect_trace(
            trace_id=trace_id,
            start_time=start_time,
            request_kwargs=request_kwargs,
            response=None,
            error=error,
        )

        # Verify error code is captured (flattened format)
        assert trace_dict["error_data"]["code"] == "rate_limit_exceeded"

    def test_build_request_data(self, collector, request_kwargs):
        """Test building request data from kwargs."""
        request_data = collector._build_request_data(request_kwargs)

        # After refactoring, _build_request_data returns dict (not dataclass)
        assert isinstance(request_data, dict)
        assert request_data["model"] == "gpt-4"
        assert len(request_data["messages"]) == 2
        assert request_data["messages"][0]["role"] == "system"
        assert request_data["messages"][1]["role"] == "user"
        assert request_data["parameters"]["temperature"] == 0.7
        assert request_data["parameters"]["max_tokens"] == 150

    def test_build_request_data_excludes_model_and_messages(self, collector):
        """Test that model and messages are not in parameters."""
        kwargs = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
            "temperature": 0.5,
        }

        request_data = collector._build_request_data(kwargs)

        # After refactoring, _build_request_data returns dict (not dataclass)
        assert "model" not in request_data["parameters"]
        assert "messages" not in request_data["parameters"]
        assert "temperature" in request_data["parameters"]

    def test_build_response_data(self, collector, mock_response):
        """Test building response data from OpenAI response."""
        response_data = collector._build_response_data(mock_response)

        # After refactoring, _build_response_data returns dict (not dataclass)
        assert isinstance(response_data, dict)
        assert response_data["id"] == "chatcmpl-abc123"
        assert response_data["model"] == "gpt-4-0613"
        assert len(response_data["choices"]) == 1
        assert response_data["choices"][0]["message"]["role"] == "assistant"
        assert response_data["usage"]["total_tokens"] == 30

    def test_build_error_data(self, collector):
        """Test building error data from exception."""
        error = ValueError("Test error message")
        error.code = "test_code"

        error_data = collector._build_error_data(error)

        # After refactoring, _build_error_data returns dict (not dataclass)
        assert isinstance(error_data, dict)
        assert error_data["type"] == "ValueError"
        assert error_data["message"] == "Test error message"
        assert error_data["code"] == "test_code"

    def test_build_error_data_without_code(self, collector):
        """Test building error data when exception has no code."""
        error = RuntimeError("Generic error")

        error_data = collector._build_error_data(error)

        # After refactoring, _build_error_data returns dict (not dataclass)
        assert error_data["type"] == "RuntimeError"
        assert error_data["message"] == "Generic error"
        assert error_data["code"] is None

    def test_collect_trace_never_raises(self, collector, config):
        """Test that collect_trace never raises exceptions."""
        # Pass invalid data that would normally cause errors
        trace_dict = collector.collect_trace(
            trace_id="test",
            start_time=time.time(),
            request_kwargs={},  # Missing required fields
            response=None,
            error=None,
        )

        # Should not raise, returns a trace with default values
        assert trace_dict is None or isinstance(trace_dict, dict)

    def test_collect_trace_handles_missing_response_fields(self, collector, config, request_kwargs):
        """Test collector handles response objects with missing fields."""
        # Create minimal response
        minimal_response = Mock()
        minimal_response.id = "test-id"
        minimal_response.model = "gpt-4"
        minimal_response.choices = []
        minimal_response.usage = None

        trace_dict = collector.collect_trace(
            trace_id="test",
            start_time=time.time(),
            request_kwargs=request_kwargs,
            response=minimal_response,
            error=None,
        )

        # Should handle gracefully (flattened format)
        assert trace_dict is not None
        assert trace_dict["response_data"]["id"] == "test-id"
        assert trace_dict["total_tokens"] == 0  # Default value when usage is None

    def test_collect_trace_handles_object_messages(self, collector, config):
        """Test collector handles message objects (not just dicts)."""
        # Some users might pass message objects
        msg_obj = Mock()
        msg_obj.role = "user"
        msg_obj.content = "Hello"

        kwargs = {"model": "gpt-4", "messages": [msg_obj]}

        trace_dict = collector.collect_trace(
            trace_id="test",
            start_time=time.time(),
            request_kwargs=kwargs,
            response=Mock(
                id="test",
                model="gpt-4",
                choices=[],
                usage=Mock(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            ),
            error=None,
        )

        # Should handle object messages (flattened format)
        assert trace_dict is not None
        assert trace_dict["request_data"]["messages"][0]["role"] == "user"
        assert trace_dict["request_data"]["messages"][0]["content"] == "Hello"

    def test_collect_trace_duration_calculation(self, collector, config, request_kwargs, mock_response):
        """Test that duration is calculated correctly."""
        start_time = time.time()
        time.sleep(0.01)  # Sleep for 10ms

        trace_dict = collector.collect_trace(
            trace_id="test",
            start_time=start_time,
            request_kwargs=request_kwargs,
            response=mock_response,
            error=None,
        )

        # Duration should be at least 10ms
        assert trace_dict["duration_ms"] >= 10

    def test_collect_trace_without_environment(self, collector, request_kwargs, mock_response):
        """Test trace collection without environment configured."""
        # No config set
        set_config(None)

        trace_dict = collector.collect_trace(
            trace_id="test",
            start_time=time.time(),
            request_kwargs=request_kwargs,
            response=mock_response,
            error=None,
        )

        # Should work without environment
        assert trace_dict is not None
        assert trace_dict.get("environment") is None

"""Tests for the Anthropic collector module."""

import time
from unittest.mock import Mock

import pytest

from ambertrace.providers.anthropic.collector import AnthropicCollector
from ambertrace.config import Config, set_config


class MockAnthropicResponse:
    """Mock Anthropic response object."""

    def __init__(self):
        self.id = "msg_abc123"
        self.model = "claude-3-opus-20240229"
        self.content = [
            Mock(type="text", text="Hello! How can I help you?")
        ]
        self.stop_reason = "end_turn"
        self.usage = Mock(input_tokens=20, output_tokens=10)


class TestAnthropicCollector:
    """Test cases for AnthropicCollector."""

    @pytest.fixture
    def collector(self):
        """Create a collector instance."""
        return AnthropicCollector()

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
            "model": "claude-3-opus-20240229",
            "messages": [
                {"role": "user", "content": "Hello!"},
            ],
            "max_tokens": 1024,
        }

    @pytest.fixture
    def request_kwargs_with_system(self):
        """Sample request kwargs with system message."""
        return {
            "model": "claude-3-sonnet-20240229",
            "system": "You are a helpful assistant.",
            "messages": [
                {"role": "user", "content": "Hello!"},
            ],
            "max_tokens": 1024,
            "temperature": 0.7,
        }

    @pytest.fixture
    def mock_response(self):
        """Create a mock Anthropic response."""
        return MockAnthropicResponse()

    def test_get_provider_name(self, collector):
        """Test that provider name is correct."""
        assert collector.get_provider_name() == "anthropic"

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
        assert trace_dict["provider"] == "anthropic"
        assert trace_dict["method"] == "messages.create"
        assert "timestamp" in trace_dict
        assert trace_dict["duration_ms"] >= 0
        assert trace_dict["environment"] == "test"
        assert trace_dict["status"] == "success"

        # Verify request data (flattened format)
        assert trace_dict["request_model"] == "claude-3-opus-20240229"
        assert trace_dict["request_data"]["model"] == "claude-3-opus-20240229"
        assert len(trace_dict["request_data"]["messages"]) == 1
        assert trace_dict["request_data"]["messages"][0]["role"] == "user"
        assert trace_dict["request_data"]["parameters"]["max_tokens"] == 1024

        # Verify response data (flattened format)
        assert trace_dict["response_data"] is not None
        assert trace_dict["response_data"]["id"] == "msg_abc123"
        assert trace_dict["response_data"]["model"] == "claude-3-opus-20240229"
        assert len(trace_dict["response_data"]["choices"]) == 1
        assert trace_dict["response_data"]["choices"][0]["message"]["role"] == "assistant"
        assert "Hello" in trace_dict["response_data"]["choices"][0]["message"]["content"]
        # Verify stop_reason normalized to finish_reason
        assert trace_dict["response_data"]["choices"][0]["finish_reason"] == "stop"
        # Verify token usage extracted to top level
        assert trace_dict["prompt_tokens"] == 20
        assert trace_dict["completion_tokens"] == 10
        assert trace_dict["total_tokens"] == 30

        # Verify error is None
        assert trace_dict["error_data"] is None

    def test_collect_trace_with_system_message(self, collector, config, request_kwargs_with_system, mock_response):
        """Test collecting a trace with system message."""
        trace_id = "test-trace-system"
        start_time = time.time()

        trace_dict = collector.collect_trace(
            trace_id=trace_id,
            start_time=start_time,
            request_kwargs=request_kwargs_with_system,
            response=mock_response,
            error=None,
        )

        # Verify system message is prepended to messages (flattened format)
        assert trace_dict is not None
        assert len(trace_dict["request_data"]["messages"]) == 2
        assert trace_dict["request_data"]["messages"][0]["role"] == "system"
        assert trace_dict["request_data"]["messages"][0]["content"] == "You are a helpful assistant."
        assert trace_dict["request_data"]["messages"][1]["role"] == "user"

        # Verify system is not in parameters
        assert "system" not in trace_dict["request_data"]["parameters"]
        assert "temperature" in trace_dict["request_data"]["parameters"]

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
        assert trace_dict["request_model"] == "claude-3-opus-20240229"
        assert trace_dict["request_data"]["model"] == "claude-3-opus-20240229"

        # Verify response is None
        assert trace_dict["response_data"] is None

        # Verify error data (flattened format)
        assert trace_dict["error_data"] is not None
        assert trace_dict["error_data"]["type"] == "ValueError"
        assert trace_dict["error_data"]["message"] == "Invalid API key"

    def test_collect_trace_with_anthropic_error_status_code(self, collector, config, request_kwargs):
        """Test collecting trace with Anthropic error that has status_code."""
        trace_id = "test-trace-with-code"
        start_time = time.time()

        # Mock error with status_code attribute
        error = ValueError("Rate limit exceeded")
        error.status_code = 429

        trace_dict = collector.collect_trace(
            trace_id=trace_id,
            start_time=start_time,
            request_kwargs=request_kwargs,
            response=None,
            error=error,
        )

        # Verify error code is captured
        assert trace_dict["error_data"]["code"] == "429"

    def test_collect_trace_with_anthropic_error_type(self, collector, config, request_kwargs):
        """Test collecting trace with Anthropic error that has type attribute."""
        trace_id = "test-trace-with-type"
        start_time = time.time()

        # Mock error with type attribute
        error = ValueError("Overloaded")
        error.type = "overloaded_error"

        trace_dict = collector.collect_trace(
            trace_id=trace_id,
            start_time=start_time,
            request_kwargs=request_kwargs,
            response=None,
            error=error,
        )

        # Verify error code from type is captured
        assert trace_dict["error_data"]["code"] == "overloaded_error"

    def test_build_request_data_excludes_model_messages_system(self, collector):
        """Test that model, messages, and system are not in parameters."""
        kwargs = {
            "model": "claude-3-opus-20240229",
            "system": "Be helpful",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 1024,
            "temperature": 0.5,
        }

        request_data = collector._build_request_data(kwargs)

        assert "model" not in request_data["parameters"]
        assert "messages" not in request_data["parameters"]
        assert "system" not in request_data["parameters"]
        assert "max_tokens" in request_data["parameters"]
        assert "temperature" in request_data["parameters"]

    def test_build_response_data_normalizes_stop_reason(self, collector):
        """Test that Anthropic stop_reason is normalized to finish_reason."""
        # Test end_turn -> stop
        response1 = Mock(id="1", model="claude", content=[], stop_reason="end_turn", usage=Mock(input_tokens=0, output_tokens=0))
        data1 = collector._build_response_data(response1)
        assert data1["choices"][0]["finish_reason"] == "stop"

        # Test max_tokens -> length
        response2 = Mock(id="2", model="claude", content=[], stop_reason="max_tokens", usage=Mock(input_tokens=0, output_tokens=0))
        data2 = collector._build_response_data(response2)
        assert data2["choices"][0]["finish_reason"] == "length"

        # Test stop_sequence -> stop
        response3 = Mock(id="3", model="claude", content=[], stop_reason="stop_sequence", usage=Mock(input_tokens=0, output_tokens=0))
        data3 = collector._build_response_data(response3)
        assert data3["choices"][0]["finish_reason"] == "stop"

        # Test unknown stop reason - pass through
        response4 = Mock(id="4", model="claude", content=[], stop_reason="tool_use", usage=Mock(input_tokens=0, output_tokens=0))
        data4 = collector._build_response_data(response4)
        assert data4["choices"][0]["finish_reason"] == "tool_use"

    def test_build_response_data_normalizes_tokens(self, collector):
        """Test that Anthropic token names are normalized to OpenAI format."""
        response = Mock(
            id="test",
            model="claude",
            content=[],
            stop_reason="end_turn",
            usage=Mock(input_tokens=100, output_tokens=50)
        )

        data = collector._build_response_data(response)

        # Verify normalized field names
        assert data["usage"]["prompt_tokens"] == 100
        assert data["usage"]["completion_tokens"] == 50
        assert data["usage"]["total_tokens"] == 150

    def test_build_response_data_handles_content_blocks(self, collector):
        """Test that content blocks are extracted correctly."""
        # Test with Mock objects
        response = Mock(
            id="test",
            model="claude",
            content=[
                Mock(type="text", text="Hello "),
                Mock(type="text", text="World!"),
            ],
            stop_reason="end_turn",
            usage=Mock(input_tokens=10, output_tokens=5)
        )

        data = collector._build_response_data(response)

        assert data["choices"][0]["message"]["content"] == "Hello World!"

    def test_build_response_data_handles_dict_content_blocks(self, collector):
        """Test that dict content blocks are extracted correctly."""
        response = Mock(
            id="test",
            model="claude",
            content=[
                {"type": "text", "text": "Dict "},
                {"type": "text", "text": "blocks!"},
            ],
            stop_reason="end_turn",
            usage=Mock(input_tokens=10, output_tokens=5)
        )

        data = collector._build_response_data(response)

        assert data["choices"][0]["message"]["content"] == "Dict blocks!"

    def test_build_error_data(self, collector):
        """Test building error data from exception."""
        error = ValueError("Test error message")
        error.status_code = 400

        error_data = collector._build_error_data(error)

        assert error_data["type"] == "ValueError"
        assert error_data["message"] == "Test error message"
        assert error_data["code"] == "400"

    def test_build_error_data_without_code(self, collector):
        """Test building error data when exception has no code."""
        error = RuntimeError("Generic error")

        error_data = collector._build_error_data(error)

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
        minimal_response.model = "claude-3"
        minimal_response.content = []
        minimal_response.stop_reason = "end_turn"
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

        kwargs = {"model": "claude-3", "messages": [msg_obj]}

        trace_dict = collector.collect_trace(
            trace_id="test",
            start_time=time.time(),
            request_kwargs=kwargs,
            response=Mock(
                id="test",
                model="claude-3",
                content=[],
                stop_reason="end_turn",
                usage=Mock(input_tokens=5, output_tokens=5),
            ),
            error=None,
        )

        # Should handle object messages (flattened format)
        assert trace_dict is not None
        assert trace_dict["request_data"]["messages"][0]["role"] == "user"
        assert trace_dict["request_data"]["messages"][0]["content"] == "Hello"

    def test_collect_trace_handles_list_content_in_messages(self, collector, config):
        """Test collector handles messages with list content (content blocks)."""
        kwargs = {
            "model": "claude-3",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Hello "},
                        {"type": "text", "text": "there!"},
                    ]
                }
            ]
        }

        trace_dict = collector.collect_trace(
            trace_id="test",
            start_time=time.time(),
            request_kwargs=kwargs,
            response=Mock(
                id="test",
                model="claude-3",
                content=[],
                stop_reason="end_turn",
                usage=Mock(input_tokens=5, output_tokens=5),
            ),
            error=None,
        )

        # Should join text blocks (flattened format)
        assert trace_dict is not None
        assert trace_dict["request_data"]["messages"][0]["content"] == "Hello  there!"

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

"""Tests for the Gemini collector module."""

import time
from unittest.mock import Mock

import pytest

from ambertrace.providers.gemini.collector import GeminiCollector
from ambertrace.config import Config, set_config


class MockGeminiResponse:
    """Mock Gemini response object."""

    def __init__(self):
        self.response_id = "gemini-resp-123"
        self.model = "gemini-pro"
        self.candidates = [
            Mock(
                content=Mock(parts=[Mock(text="Hello! How can I help you?")]),
                finish_reason="STOP",
            )
        ]
        self.usage_metadata = Mock(
            prompt_token_count=15,
            candidates_token_count=8,
            total_token_count=23,
        )
        self.text = "Hello! How can I help you?"


class TestGeminiCollector:
    """Test cases for GeminiCollector."""

    @pytest.fixture
    def collector(self):
        """Create a collector instance."""
        return GeminiCollector()

    @pytest.fixture
    def config(self):
        """Setup test configuration."""
        config = Config(api_key="test_key", environment="test")
        set_config(config)
        yield config
        set_config(None)

    @pytest.fixture
    def request_kwargs(self):
        """Sample request kwargs for original SDK (model injected by interceptor)."""
        return {
            "_ambertrace_model": "gemini-pro",
            "contents": "Hello!",
        }

    @pytest.fixture
    def request_kwargs_newer_sdk(self):
        """Sample request kwargs for newer SDK (model as kwarg)."""
        return {
            "model": "gemini-2.0-flash",
            "contents": "Hello!",
        }

    @pytest.fixture
    def mock_response(self):
        """Create a mock Gemini response."""
        return MockGeminiResponse()

    def test_get_provider_name(self, collector):
        """Test that provider name is correct."""
        assert collector.get_provider_name() == "gemini"

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

        assert trace_dict is not None
        assert trace_dict["trace_id"] == trace_id
        assert trace_dict["provider"] == "gemini"
        assert trace_dict["method"] == "generate_content"
        assert "timestamp" in trace_dict
        assert trace_dict["duration_ms"] >= 0
        assert trace_dict["environment"] == "test"
        assert trace_dict["status"] == "success"

        # Verify request data (flattened format)
        assert trace_dict["request_model"] == "gemini-pro"
        assert trace_dict["request_data"]["model"] == "gemini-pro"
        assert len(trace_dict["request_data"]["messages"]) == 1
        assert trace_dict["request_data"]["messages"][0]["role"] == "user"
        assert trace_dict["request_data"]["messages"][0]["content"] == "Hello!"

        # Verify response data (flattened format)
        assert trace_dict["response_data"] is not None
        assert trace_dict["response_data"]["id"] == "gemini-resp-123"
        assert trace_dict["response_data"]["model"] == "gemini-pro"
        assert len(trace_dict["response_data"]["choices"]) == 1
        assert trace_dict["response_data"]["choices"][0]["message"]["role"] == "assistant"
        assert "Hello" in trace_dict["response_data"]["choices"][0]["message"]["content"]
        assert trace_dict["response_data"]["choices"][0]["finish_reason"] == "stop"

        # Verify token extraction (flattened format)
        assert trace_dict["prompt_tokens"] == 15
        assert trace_dict["completion_tokens"] == 8
        assert trace_dict["total_tokens"] == 23

        # Verify error is None
        assert trace_dict["error_data"] is None

    def test_collect_trace_with_string_contents(self, collector, config):
        """Test collecting trace when contents is a bare string."""
        kwargs = {"_ambertrace_model": "gemini-pro", "contents": "Tell me a joke"}
        response = MockGeminiResponse()

        trace_dict = collector.collect_trace(
            trace_id="test-string",
            start_time=time.time(),
            request_kwargs=kwargs,
            response=response,
        )

        assert trace_dict is not None
        assert len(trace_dict["request_data"]["messages"]) == 1
        assert trace_dict["request_data"]["messages"][0]["role"] == "user"
        assert trace_dict["request_data"]["messages"][0]["content"] == "Tell me a joke"

    def test_collect_trace_with_list_contents(self, collector, config):
        """Test collecting trace when contents is a list of Content objects."""
        content_obj1 = Mock(role="user", parts=[Mock(text="Hello")])
        content_obj2 = Mock(role="model", parts=[Mock(text="Hi there")])
        kwargs = {
            "_ambertrace_model": "gemini-pro",
            "contents": [content_obj1, content_obj2],
        }
        response = MockGeminiResponse()

        trace_dict = collector.collect_trace(
            trace_id="test-list",
            start_time=time.time(),
            request_kwargs=kwargs,
            response=response,
        )

        assert trace_dict is not None
        assert len(trace_dict["request_data"]["messages"]) == 2
        assert trace_dict["request_data"]["messages"][0]["role"] == "user"
        assert trace_dict["request_data"]["messages"][0]["content"] == "Hello"
        assert trace_dict["request_data"]["messages"][1]["role"] == "model"
        assert trace_dict["request_data"]["messages"][1]["content"] == "Hi there"

    def test_collect_trace_with_dict_contents(self, collector, config):
        """Test collecting trace when contents is a list of dicts."""
        kwargs = {
            "_ambertrace_model": "gemini-pro",
            "contents": [
                {"role": "user", "parts": [{"text": "What is Python?"}]},
                {"role": "model", "parts": [{"text": "A programming language"}]},
            ],
        }
        response = MockGeminiResponse()

        trace_dict = collector.collect_trace(
            trace_id="test-dict",
            start_time=time.time(),
            request_kwargs=kwargs,
            response=response,
        )

        assert trace_dict is not None
        assert len(trace_dict["request_data"]["messages"]) == 2
        assert trace_dict["request_data"]["messages"][0]["content"] == "What is Python?"
        assert trace_dict["request_data"]["messages"][1]["content"] == "A programming language"

    def test_collect_trace_with_parts_contents(self, collector, config):
        """Test collecting trace when contents is a list of Part objects."""
        part1 = Mock(spec=[])
        part1.text = "Part one"
        part2 = Mock(spec=[])
        part2.text = "Part two"
        kwargs = {
            "_ambertrace_model": "gemini-pro",
            "contents": [part1, part2],
        }
        response = MockGeminiResponse()

        trace_dict = collector.collect_trace(
            trace_id="test-parts",
            start_time=time.time(),
            request_kwargs=kwargs,
            response=response,
        )

        assert trace_dict is not None
        # Each Part becomes a separate user message (flattened format)
        assert len(trace_dict["request_data"]["messages"]) == 2
        assert trace_dict["request_data"]["messages"][0]["content"] == "Part one"
        assert trace_dict["request_data"]["messages"][1]["content"] == "Part two"

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

        assert trace_dict is not None
        assert trace_dict["trace_id"] == trace_id
        assert trace_dict["status"] == "error"
        assert trace_dict["request_model"] == "gemini-pro"
        assert trace_dict["request_data"]["model"] == "gemini-pro"
        assert trace_dict["response_data"] is None
        assert trace_dict["error_data"] is not None
        assert trace_dict["error_data"]["type"] == "ValueError"
        assert trace_dict["error_data"]["message"] == "Invalid API key"

    def test_collect_trace_with_status_code_error(self, collector, config, request_kwargs):
        """Test collecting trace with error that has status_code."""
        error = ValueError("Rate limit exceeded")
        error.status_code = 429

        trace_dict = collector.collect_trace(
            trace_id="test-error-code",
            start_time=time.time(),
            request_kwargs=request_kwargs,
            response=None,
            error=error,
        )

        assert trace_dict["error_data"]["code"] == "429"

    def test_build_request_excludes_sensitive_keys(self, collector):
        """Test that sensitive keys are excluded from parameters."""
        kwargs = {
            "model": "gemini-pro",
            "contents": "Hello",
            "_ambertrace_model": "gemini-pro",
            "api_key": "secret-key-12345",
            "credentials": {"token": "secret"},
            "client": Mock(),
            "_client": Mock(),
            "temperature": 0.7,
            "max_output_tokens": 1024,
        }

        request_data = collector._build_request_data(kwargs)

        # Security: sensitive keys must NOT appear in parameters
        assert "api_key" not in request_data["parameters"]
        assert "credentials" not in request_data["parameters"]
        assert "client" not in request_data["parameters"]
        assert "_client" not in request_data["parameters"]
        assert "model" not in request_data["parameters"]
        assert "contents" not in request_data["parameters"]
        assert "_ambertrace_model" not in request_data["parameters"]

        # Non-sensitive params should be included
        assert "temperature" in request_data["parameters"]
        assert "max_output_tokens" in request_data["parameters"]

    def test_api_key_not_leaked_in_trace(self, collector, config):
        """Security test: API key must never appear anywhere in the trace."""
        secret_key = "AIzaSyD_SUPER_SECRET_KEY_12345"
        kwargs = {
            "model": "gemini-pro",
            "contents": "Hello",
            "api_key": secret_key,
        }
        response = MockGeminiResponse()

        trace_dict = collector.collect_trace(
            trace_id="test-security",
            start_time=time.time(),
            request_kwargs=kwargs,
            response=response,
        )

        # Convert entire trace to string and search for the key
        import json

        trace_str = json.dumps(trace_dict, default=str)
        assert secret_key not in trace_str

    def test_normalize_finish_reason(self, collector):
        """Test finish reason normalization for various values."""
        assert collector._normalize_finish_reason("STOP") == "stop"
        assert collector._normalize_finish_reason("MAX_TOKENS") == "length"
        assert collector._normalize_finish_reason("SAFETY") == "content_filter"
        assert collector._normalize_finish_reason("RECITATION") == "content_filter"
        assert collector._normalize_finish_reason("OTHER") == "stop"
        assert collector._normalize_finish_reason(None) == "stop"

        # Integer enum values
        assert collector._normalize_finish_reason(1) == "stop"
        assert collector._normalize_finish_reason(2) == "length"
        assert collector._normalize_finish_reason(3) == "content_filter"

    def test_normalize_tokens(self, collector):
        """Test that Gemini token field names are normalized."""
        response = Mock(
            response_id="test",
            model="gemini-pro",
            candidates=[],
            text="Hello",
            usage_metadata=Mock(
                prompt_token_count=100,
                candidates_token_count=50,
                total_token_count=150,
            ),
        )

        data = collector._build_response_data(response)

        assert data["usage"]["prompt_tokens"] == 100
        assert data["usage"]["completion_tokens"] == 50
        assert data["usage"]["total_tokens"] == 150

    def test_multiple_candidates(self, collector, config):
        """Test handling multiple candidates in response."""
        response = Mock(
            response_id="test",
            model="gemini-pro",
            candidates=[
                Mock(
                    content=Mock(parts=[Mock(text="Response 1")]),
                    finish_reason="STOP",
                ),
                Mock(
                    content=Mock(parts=[Mock(text="Response 2")]),
                    finish_reason="STOP",
                ),
            ],
            usage_metadata=Mock(
                prompt_token_count=10,
                candidates_token_count=20,
                total_token_count=30,
            ),
        )

        kwargs = {"_ambertrace_model": "gemini-pro", "contents": "Hello"}
        trace_dict = collector.collect_trace(
            trace_id="test-multi",
            start_time=time.time(),
            request_kwargs=kwargs,
            response=response,
        )

        assert trace_dict is not None
        assert len(trace_dict["response_data"]["choices"]) == 2
        assert trace_dict["response_data"]["choices"][0]["index"] == 0
        assert trace_dict["response_data"]["choices"][0]["message"]["content"] == "Response 1"
        assert trace_dict["response_data"]["choices"][1]["index"] == 1
        assert trace_dict["response_data"]["choices"][1]["message"]["content"] == "Response 2"

    def test_missing_fields_graceful(self, collector, config):
        """Test graceful handling of missing response fields."""
        # Response with no candidates, no usage
        minimal_response = Mock(spec=[])
        minimal_response.response_id = None
        minimal_response.model = None
        minimal_response.candidates = None
        minimal_response.usage_metadata = None
        minimal_response.text = None

        kwargs = {"_ambertrace_model": "gemini-pro", "contents": "Hello"}
        trace_dict = collector.collect_trace(
            trace_id="test-minimal",
            start_time=time.time(),
            request_kwargs=kwargs,
            response=minimal_response,
        )

        assert trace_dict is not None
        assert trace_dict["response_data"]["id"] == "unknown"
        assert trace_dict["response_data"]["model"] == "unknown"
        assert trace_dict["prompt_tokens"] == 0
        assert trace_dict["completion_tokens"] == 0

    def test_collect_trace_never_raises(self, collector, config):
        """Test that collect_trace never raises exceptions."""
        # Pass invalid data
        trace_dict = collector.collect_trace(
            trace_id="test",
            start_time=time.time(),
            request_kwargs={},
            response=None,
            error=None,
        )
        assert trace_dict is None or isinstance(trace_dict, dict)

    def test_duration_calculation(self, collector, config, request_kwargs, mock_response):
        """Test that duration is calculated correctly."""
        start_time = time.time()
        time.sleep(0.01)  # Sleep for 10ms

        trace_dict = collector.collect_trace(
            trace_id="test",
            start_time=start_time,
            request_kwargs=request_kwargs,
            response=mock_response,
        )

        assert trace_dict["duration_ms"] >= 10

    def test_status_field(self, collector, config, request_kwargs, mock_response):
        """Test status field is set correctly."""
        trace_dict = collector.collect_trace(
            trace_id="test",
            start_time=time.time(),
            request_kwargs=request_kwargs,
            response=mock_response,
        )

        assert trace_dict["status"] == "success"

    def test_timestamp_iso_format(self, collector, config, request_kwargs, mock_response):
        """Test timestamp is in ISO 8601 format."""
        trace_dict = collector.collect_trace(
            trace_id="test",
            start_time=time.time(),
            request_kwargs=request_kwargs,
            response=mock_response,
        )

        # Verify ISO 8601 format
        timestamp = trace_dict["timestamp"]
        assert "T" in timestamp
        assert len(timestamp) > 10  # Not just a date

    def test_collect_trace_without_environment(self, collector, request_kwargs, mock_response):
        """Test trace collection without environment configured."""
        set_config(None)

        trace_dict = collector.collect_trace(
            trace_id="test",
            start_time=time.time(),
            request_kwargs=request_kwargs,
            response=mock_response,
        )

        assert trace_dict is not None
        assert trace_dict.get("environment") is None

    def test_model_from_newer_sdk_kwargs(self, collector, config, request_kwargs_newer_sdk, mock_response):
        """Test model extraction from newer SDK kwargs (model as kwarg)."""
        trace_dict = collector.collect_trace(
            trace_id="test",
            start_time=time.time(),
            request_kwargs=request_kwargs_newer_sdk,
            response=mock_response,
        )

        assert trace_dict is not None
        assert trace_dict["request_model"] == "gemini-2.0-flash"
        assert trace_dict["request_data"]["model"] == "gemini-2.0-flash"

    def test_extract_text_from_parts_strings(self, collector):
        """Test extracting text from string parts."""
        result = collector._extract_text_from_parts(["Hello", "World"])
        assert result == "Hello World"

    def test_extract_text_from_parts_dicts(self, collector):
        """Test extracting text from dict parts."""
        result = collector._extract_text_from_parts([
            {"text": "Hello"},
            {"text": "World"},
        ])
        assert result == "Hello World"

    def test_extract_text_from_parts_objects(self, collector):
        """Test extracting text from Part objects."""
        result = collector._extract_text_from_parts([
            Mock(text="Hello"),
            Mock(text="World"),
        ])
        assert result == "Hello World"

    def test_extract_text_from_parts_single_string(self, collector):
        """Test extracting text when parts is a single string."""
        result = collector._extract_text_from_parts("Just a string")
        assert result == "Just a string"

    def test_contents_none(self, collector):
        """Test normalizing None contents."""
        messages = collector._normalize_contents(None)
        assert messages == []

    def test_error_with_reason_attribute(self, collector, config, request_kwargs):
        """Test error data extraction with reason attribute."""
        error = ValueError("Something went wrong")
        error.reason = "PERMISSION_DENIED"

        trace_dict = collector.collect_trace(
            trace_id="test-reason",
            start_time=time.time(),
            request_kwargs=request_kwargs,
            response=None,
            error=error,
        )

        assert trace_dict["error_data"]["code"] == "PERMISSION_DENIED"

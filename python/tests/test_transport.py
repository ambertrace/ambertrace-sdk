"""Tests for the transport module."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import respx

from ambertrace.config import Config, set_config
from ambertrace.transport import Transport


class TestTransport:
    """Test cases for Transport class."""

    @pytest.fixture
    def config(self):
        """Setup test configuration."""
        config = Config(
            api_key="test_api_key_1234567890",
            base_url="https://test.ambertrace.dev",
            timeout=2.0,
        )
        set_config(config)
        yield config
        set_config(None)

    @pytest.fixture
    def transport(self):
        """Create a transport instance."""
        transport = Transport()
        yield transport
        transport.stop()

    @pytest.fixture
    def sample_trace(self):
        """Create a sample trace dictionary."""
        return {
            "trace_id": "test-trace-123",
            "timestamp": "2024-01-01T00:00:00Z",
            "provider": "openai",
            "method": "chat.completions.create",
            "duration_ms": 123.45,
            "request": {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello"}],
                "parameters": {},
            },
            "response": {
                "id": "chatcmpl-123",
                "model": "gpt-4",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hi!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            },
            "error": None,
            "sdk_version": "ambertrace-python/0.1.0",
            "environment": "test",
        }

    def test_transport_initialization(self, transport):
        """Test transport initializes correctly."""
        assert transport._executor is None
        assert transport._shutdown is False
        assert transport._queue.maxsize == Transport.MAX_QUEUE_SIZE

    def test_transport_start(self, transport):
        """Test starting the transport."""
        transport.start()

        assert transport._executor is not None
        assert transport._shutdown is False

        transport.stop()

    def test_transport_stop(self, transport):
        """Test stopping the transport."""
        transport.start()
        transport.stop()

        assert transport._executor is None
        assert transport._shutdown is True

    def test_start_idempotent(self, transport):
        """Test calling start multiple times is safe."""
        transport.start()
        executor1 = transport._executor

        transport.start()
        executor2 = transport._executor

        # Should not create new executor
        assert executor1 is executor2

        transport.stop()

    @respx.mock
    def test_send_trace_success(self, config, transport, sample_trace):
        """Test successfully sending a trace."""
        # Mock the HTTP endpoint
        route = respx.post("https://test.ambertrace.dev/api/traces/ingest").mock(
            return_value=httpx.Response(201)
        )

        transport.start()
        transport.send_trace(sample_trace)

        # Wait for background thread to complete
        transport.flush(timeout=2.0)

        # Verify request was made
        assert route.called

    @respx.mock
    def test_send_trace_includes_auth_header(self, config, transport, sample_trace):
        """Test that Authorization header is included."""
        route = respx.post("https://test.ambertrace.dev/api/traces/ingest").mock(
            return_value=httpx.Response(201)
        )

        transport.start()
        transport.send_trace(sample_trace)
        transport.flush(timeout=2.0)

        # Check headers
        assert route.called
        request = route.calls.last.request
        assert "Authorization" in request.headers
        assert request.headers["Authorization"] == "Bearer test_api_key_1234567890"

    @respx.mock
    def test_send_trace_handles_401(self, config, transport, sample_trace):
        """Test handling of 401 Unauthorized."""
        respx.post("https://test.ambertrace.dev/api/traces/ingest").mock(
            return_value=httpx.Response(401, json={"error": "Invalid API key"})
        )

        transport.start()

        # Should not raise
        transport.send_trace(sample_trace)
        transport.flush(timeout=2.0)

        # Test passes if no exception raised

    @respx.mock
    def test_send_trace_handles_500(self, config, transport, sample_trace):
        """Test handling of 500 server error."""
        respx.post("https://test.ambertrace.dev/api/traces/ingest").mock(
            return_value=httpx.Response(500, json={"error": "Internal server error"})
        )

        transport.start()

        # Should not raise
        transport.send_trace(sample_trace)
        transport.flush(timeout=2.0)

    @respx.mock
    def test_send_trace_handles_timeout(self, config, transport, sample_trace):
        """Test handling of network timeout."""

        def timeout_callback(request):
            raise httpx.TimeoutException("Request timed out")

        respx.post("https://test.ambertrace.dev/api/traces/ingest").mock(side_effect=timeout_callback)

        transport.start()

        # Should not raise
        transport.send_trace(sample_trace)
        transport.flush(timeout=2.0)

    def test_send_trace_when_shutdown(self, transport, sample_trace):
        """Test sending trace when transport is shutdown."""
        transport.start()
        transport.stop()

        # Should not raise
        transport.send_trace(sample_trace)

    def test_send_trace_when_not_started(self, transport, sample_trace):
        """Test sending trace before transport is started."""
        # Should not raise
        transport.send_trace(sample_trace)

    def test_queue_drops_oldest_when_full(self, config, transport):
        """Test that queue drops oldest trace when full."""
        transport.start()

        # Fill queue beyond capacity
        for i in range(Transport.MAX_QUEUE_SIZE + 10):
            trace = {"trace_id": f"trace-{i}", "timestamp": "2024-01-01T00:00:00Z"}
            transport.send_trace(trace)

        # Queue should not exceed max size
        assert transport._queue.qsize() <= Transport.MAX_QUEUE_SIZE

        transport.stop()

    def test_flush_waits_for_completion(self, config, transport, sample_trace):
        """Test flush waits for traces to be sent."""
        with respx.mock:
            respx.post("https://test.ambertrace.dev/api/traces/ingest").mock(
                return_value=httpx.Response(201)
            )

            transport.start()
            transport.send_trace(sample_trace)

            # Flush should wait
            transport.flush(timeout=2.0)

            # After flush, future should be done
            # (We can't easily verify this without accessing internals)

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_trace_async_success(self, config, transport, sample_trace):
        """Test async trace sending."""
        route = respx.post("https://test.ambertrace.dev/api/traces/ingest").mock(
            return_value=httpx.Response(201)
        )

        transport.start()
        transport.send_trace_async(sample_trace)

        # Wait for async task
        await transport.flush_async(timeout=2.0)

        # Verify request was made
        assert route.called

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_trace_async_handles_errors(self, config, transport, sample_trace):
        """Test async trace sending handles errors gracefully."""
        respx.post("https://test.ambertrace.dev/api/traces/ingest").mock(
            return_value=httpx.Response(500)
        )

        transport.start()

        # Should not raise
        transport.send_trace_async(sample_trace)
        await transport.flush_async(timeout=2.0)

    @pytest.mark.asyncio
    async def test_send_trace_async_when_shutdown(self, transport, sample_trace):
        """Test async send when transport is shutdown."""
        transport.start()
        transport.stop()

        # Should not raise
        transport.send_trace_async(sample_trace)

    @pytest.mark.asyncio
    @respx.mock
    async def test_flush_async_waits_for_tasks(self, config, sample_trace):
        """Test async flush waits for all tasks."""
        route = respx.post("https://test.ambertrace.dev/api/traces/ingest").mock(
            return_value=httpx.Response(201)
        )

        # Create a fresh transport for this test to avoid state leakage
        transport = Transport()
        transport.start()

        try:
            # Send multiple traces
            for i in range(3):
                trace = sample_trace.copy()
                trace["trace_id"] = f"trace-{i}"
                transport.send_trace_async(trace)

            # Flush and wait
            await transport.flush_async(timeout=5.0)

            # All should be sent
            assert route.call_count >= 3  # At least 3 calls
        finally:
            transport.stop()

    @pytest.mark.asyncio
    async def test_flush_async_handles_timeout(self, config, transport, sample_trace):
        """Test async flush handles timeout gracefully."""

        async def slow_response(request):
            await asyncio.sleep(10)  # Longer than timeout
            return httpx.Response(201)

        with respx.mock:
            respx.post("https://test.ambertrace.dev/api/traces/ingest").mock(side_effect=slow_response)

            transport.start()
            transport.send_trace_async(sample_trace)

            # Should timeout but not raise
            await transport.flush_async(timeout=0.5)

    def test_flush_without_transport_started(self, transport):
        """Test flush when transport hasn't been started."""
        # Should not raise
        transport.flush(timeout=1.0)

    @pytest.mark.asyncio
    async def test_flush_async_without_transport_started(self, transport):
        """Test async flush when transport hasn't been started."""
        # Should not raise
        await transport.flush_async(timeout=1.0)

    @respx.mock
    def test_send_trace_includes_user_agent(self, config, transport, sample_trace):
        """Test that User-Agent header is included."""
        route = respx.post("https://test.ambertrace.dev/api/traces/ingest").mock(
            return_value=httpx.Response(201)
        )

        transport.start()
        transport.send_trace(sample_trace)
        transport.flush(timeout=2.0)

        # Check User-Agent
        assert route.called
        request = route.calls.last.request
        assert "User-Agent" in request.headers
        assert "ambertrace-python" in request.headers["User-Agent"]

    @respx.mock
    def test_send_trace_posts_correct_json(self, config, transport, sample_trace):
        """Test that trace is sent as JSON body."""
        route = respx.post("https://test.ambertrace.dev/api/traces/ingest").mock(
            return_value=httpx.Response(201)
        )

        transport.start()
        transport.send_trace(sample_trace)
        transport.flush(timeout=2.0)

        # Verify JSON body
        assert route.called
        request = route.calls.last.request
        assert request.headers["Content-Type"] == "application/json"

        # Body should match sample trace
        import json

        body = json.loads(request.content)
        assert body["trace_id"] == sample_trace["trace_id"]
        assert body["provider"] == "openai"

"""Base classes for provider-specific interceptors and collectors.

This module defines the abstract interfaces that all LLM provider implementations
must follow. This enables clean separation between providers (OpenAI, Anthropic, etc.)
while maintaining a consistent API.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ambertrace._version import __version__
from ambertrace.models import (
    Choice,
    ErrorData,
    Message,
    RequestData,
    ResponseData,
    Trace,
    UsageData,
)

logger = logging.getLogger(__name__)


class BaseInterceptor(ABC):
    """Base class for provider-specific interceptors.

    Each provider (OpenAI, Anthropic, etc.) implements this interface to handle
    monkey-patching of their respective SDK methods.
    """

    @abstractmethod
    def patch(self) -> None:
        """Apply monkey-patches to the provider's SDK.

        This method wraps the provider's API methods to intercept calls and
        collect traces. It should be idempotent - calling it multiple times
        should be safe.

        The implementation should:
        - Store references to original methods
        - Replace methods with wrapped versions
        - Handle missing SDK gracefully (log warning, don't raise)
        """
        pass

    @abstractmethod
    def unpatch(self) -> None:
        """Remove monkey-patches and restore original SDK methods.

        This method should restore the provider's SDK to its original state
        by replacing wrapped methods with the original references.

        The implementation should:
        - Restore all original method references
        - Clean up any state
        - Handle errors gracefully (log, don't raise)
        """
        pass

    @abstractmethod
    def is_patched(self) -> bool:
        """Check if patches are currently applied.

        Returns:
            True if the provider's SDK is currently patched, False otherwise
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name (e.g., 'openai', 'anthropic').

        Returns:
            Provider name as a string (lowercase, no spaces)
        """
        pass


class BaseCollector(ABC):
    """Base class for provider-specific trace collectors.

    Each provider implements this interface to extract and serialize trace data
    from their specific response formats into a unified trace format.

    The recommended pattern for implementing collect_trace():
    1. Extract provider-specific data into normalized dicts
    2. Call self.build_trace() with the normalized data
    3. build_trace() handles dataclass creation and serialization
    """

    @abstractmethod
    def collect_trace(
        self,
        trace_id: str,
        start_time: float,
        request_kwargs: Dict[str, Any],
        response: Optional[Any] = None,
        error: Optional[Exception] = None,
    ) -> Optional[Dict[str, Any]]:
        """Collect and serialize a trace from an LLM API call.

        This method extracts relevant data from the provider's request/response
        objects and builds a standardized trace dictionary.

        Args:
            trace_id: Unique identifier for this trace (UUID)
            start_time: Start timestamp from time.time()
            request_kwargs: Keyword arguments passed to the provider's API
            response: Provider's response object (if successful)
            error: Exception object (if call failed)

        Returns:
            Serialized trace as dictionary, or None if collection fails.
            Should call self.build_trace() to ensure consistent output format.

        Note:
            This method must NEVER raise exceptions. All errors should be
            caught, logged, and None should be returned.
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name (e.g., 'openai', 'anthropic').

        Returns:
            Provider name as a string (lowercase, no spaces)
        """
        pass

    def build_trace(
        self,
        trace_id: str,
        timestamp: str,
        provider: str,
        method: str,
        duration_ms: float,
        request_data: Dict[str, Any],
        response_data: Optional[Dict[str, Any]] = None,
        error_data: Optional[Dict[str, Any]] = None,
        environment: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Build trace using shared dataclasses and serialize to backend format.

        This method provides a unified way to build traces across all providers.
        Provider-specific collectors should extract data into the normalized dict
        format and call this method to create the final trace.

        Args:
            trace_id: Unique trace identifier (UUID)
            timestamp: ISO 8601 timestamp string
            provider: Provider name (e.g., 'openai', 'anthropic', 'gemini')
            method: API method name (e.g., 'chat.completions.create')
            duration_ms: Call duration in milliseconds
            request_data: Normalized request dict with keys:
                - model: str
                - messages: List[{role: str, content: str}]
                - parameters: Dict[str, Any] (optional)
            response_data: Normalized response dict with keys (optional):
                - id: str
                - model: str
                - choices: List[{index: int, message: {role, content}, finish_reason: str}]
                - usage: {prompt_tokens: int, completion_tokens: int, total_tokens: int}
            error_data: Normalized error dict with keys (optional):
                - type: str
                - message: str
                - code: str | None
            environment: Environment name (optional)

        Returns:
            Serialized trace dict matching backend TraceCreate schema,
            or None if building fails.
        """
        try:
            # Convert request dict to dataclass
            messages = [
                Message(role=m.get("role", "unknown"), content=m.get("content", ""))
                for m in request_data.get("messages", [])
            ]
            request = RequestData(
                model=request_data.get("model", "unknown"),
                messages=messages,
                parameters=request_data.get("parameters", {}),
            )

            # Convert response dict to dataclass (if present)
            response = None
            if response_data:
                choices = []
                for c in response_data.get("choices", []):
                    msg = c.get("message", {})
                    choices.append(
                        Choice(
                            index=c.get("index", 0),
                            message=Message(
                                role=msg.get("role", "assistant"),
                                content=msg.get("content", ""),
                            ),
                            finish_reason=c.get("finish_reason", "unknown"),
                        )
                    )

                usage_dict = response_data.get("usage", {})
                usage = UsageData(
                    prompt_tokens=usage_dict.get("prompt_tokens", 0),
                    completion_tokens=usage_dict.get("completion_tokens", 0),
                    total_tokens=usage_dict.get("total_tokens", 0),
                )

                response = ResponseData(
                    id=response_data.get("id", "unknown"),
                    model=response_data.get("model", "unknown"),
                    choices=choices,
                    usage=usage,
                )

            # Convert error dict to dataclass (if present)
            error = None
            if error_data:
                error = ErrorData(
                    type=error_data.get("type", "unknown"),
                    message=error_data.get("message", ""),
                    code=error_data.get("code"),
                )

            # Build trace dataclass
            trace = Trace(
                trace_id=trace_id,
                timestamp=timestamp,
                provider=provider,
                method=method,
                duration_ms=duration_ms,
                request=request,
                response=response,
                error=error,
                sdk_version=f"ambertrace-python/{__version__}",
                environment=environment,
            )

            # Serialize to backend format
            return trace.to_dict()

        except Exception as e:
            logger.error(f"Failed to build trace {trace_id}: {e}", exc_info=True)
            return None

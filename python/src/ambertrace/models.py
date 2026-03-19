"""Data models for AmberTrace traces."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    """Represents a chat message in the conversation."""

    role: str  # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "role": self.role,
            "content": self.content,
        }


@dataclass
class RequestData:
    """Request data sent to the LLM."""

    model: str
    messages: List[Message]
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "model": self.model,
            "messages": [msg.to_dict() for msg in self.messages],
            "parameters": self.parameters,
        }


@dataclass
class Choice:
    """Represents a single choice in the LLM response."""

    index: int
    message: Message
    finish_reason: str  # "stop" | "length" | "content_filter"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "index": self.index,
            "message": self.message.to_dict(),
            "finish_reason": self.finish_reason,
        }


@dataclass
class UsageData:
    """Token usage statistics from the LLM response."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class ResponseData:
    """Response data received from the LLM."""

    id: str  # OpenAI response ID
    model: str  # Actual model used (may differ from request)
    choices: List[Choice]
    usage: UsageData

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "model": self.model,
            "choices": [choice.to_dict() for choice in self.choices],
            "usage": self.usage.to_dict(),
        }


@dataclass
class ErrorData:
    """Error information when LLM call fails."""

    type: str  # Exception class name
    message: str
    code: Optional[str] = None  # OpenAI error code if available

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: Dict[str, Any] = {
            "type": self.type,
            "message": self.message,
        }
        if self.code is not None:
            result["code"] = self.code
        return result


@dataclass
class Trace:
    """Main trace object containing all trace data."""

    # Required fields
    trace_id: str  # UUID v4
    timestamp: str  # ISO 8601 UTC
    provider: str  # "openai" (hardcoded for MVP)
    method: str  # "chat.completions.create"
    duration_ms: float  # Wall-clock time in milliseconds

    # Request data
    request: RequestData

    # Response data (mutually exclusive with error)
    response: Optional[ResponseData] = None

    # Error data (mutually exclusive with response)
    error: Optional[ErrorData] = None

    # Metadata
    sdk_version: str = ""
    environment: Optional[str] = None
    service_name: Optional[str] = None
    trace_session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns flattened format matching backend TraceCreate schema:
        - request_model: extracted from request
        - request_data: full request dict
        - response_data: full response dict (or None)
        - error_data: full error dict (or None)
        - prompt_tokens, completion_tokens, total_tokens: extracted from usage
        - status: "success" or "error"
        """
        # Extract tokens from response usage
        prompt_tokens = None
        completion_tokens = None
        total_tokens = None
        if self.response and self.response.usage:
            prompt_tokens = self.response.usage.prompt_tokens
            completion_tokens = self.response.usage.completion_tokens
            total_tokens = self.response.usage.total_tokens

        # Determine status
        status = "error" if self.error else "success"

        result: Dict[str, Any] = {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "provider": self.provider,
            "method": self.method,
            "duration_ms": self.duration_ms,
            "request_model": self.request.model,
            "request_data": self.request.to_dict(),
            "response_data": self.response.to_dict() if self.response else None,
            "error_data": self.error.to_dict() if self.error else None,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "status": status,
            "environment": self.environment,
            "service_name": self.service_name,
            "trace_session_id": self.trace_session_id,
            "sdk_version": self.sdk_version,
        }

        return result

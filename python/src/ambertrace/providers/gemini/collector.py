"""Trace collection and serialization for Google Gemini."""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ambertrace.config import get_config
from ambertrace.providers.base import BaseCollector

logger = logging.getLogger(__name__)

# Keys that must never appear in trace parameters (security)
_EXCLUDED_PARAM_KEYS = {
    "model",
    "contents",
    "_ambertrace_model",
    "api_key",
    "credentials",
    "client",
    "_client",
}

# Gemini finish reason normalization map
_FINISH_REASON_MAP = {
    # String enum values
    "STOP": "stop",
    "MAX_TOKENS": "length",
    "SAFETY": "content_filter",
    "RECITATION": "content_filter",
    "OTHER": "stop",
    "FINISH_REASON_UNSPECIFIED": "stop",
    # Integer enum values (older SDK)
    0: "stop",  # FINISH_REASON_UNSPECIFIED
    1: "stop",  # STOP
    2: "length",  # MAX_TOKENS
    3: "content_filter",  # SAFETY
    4: "content_filter",  # RECITATION
    5: "stop",  # OTHER
}


class GeminiCollector(BaseCollector):
    """Collects and builds trace objects from Google Gemini API calls.

    This class is responsible for:
    - Extracting data from Gemini request/response objects
    - Normalizing to unified dict format
    - Calling build_trace() for dataclass creation and serialization
    - Never raising exceptions (defensive error handling)
    """

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "google"

    def collect_trace(
        self,
        trace_id: str,
        start_time: float,
        request_kwargs: Dict[str, Any],
        response: Optional[Any] = None,
        error: Optional[Exception] = None,
    ) -> Optional[Dict[str, Any]]:
        """Collect and serialize a trace from a Gemini API call.

        Args:
            trace_id: Unique trace identifier (UUID)
            start_time: Start timestamp from time.time()
            request_kwargs: Kwargs passed to Gemini API call
            response: Gemini response object (if successful)
            error: Exception object (if call failed)

        Returns:
            Serialized trace as dictionary, or None if collection fails
        """
        try:
            # Calculate duration
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            # Get current timestamp in ISO 8601 UTC format
            timestamp = datetime.now(timezone.utc).isoformat()

            # Get configuration
            config = get_config()
            environment = config.environment if config else None

            # Build normalized data dicts
            request_data = self._build_request_data(request_kwargs)
            response_data = None
            error_data = None

            if response is not None:
                response_data = self._build_response_data(response)
            elif error is not None:
                error_data = self._build_error_data(error)

            # Use shared build_trace() for dataclass creation and serialization
            trace_dict = self.build_trace(
                trace_id=trace_id,
                timestamp=timestamp,
                provider="google",
                method="generate_content",
                duration_ms=duration_ms,
                request_data=request_data,
                response_data=response_data,
                error_data=error_data,
                environment=environment,
            )

            if trace_dict:
                logger.debug(f"Collected Gemini trace {trace_id} (duration: {duration_ms:.2f}ms)")

            return trace_dict

        except Exception as e:
            # Never raise exceptions - log and return None
            logger.error(f"Failed to collect Gemini trace {trace_id}: {e}", exc_info=True)
            return None

    def _build_request_data(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Build request data dict from Gemini API call kwargs.

        Args:
            kwargs: Keyword arguments passed to Gemini API

        Returns:
            Normalized request data dict
        """
        # Extract model (may come from _ambertrace_model injected by interceptor,
        # or from 'model' kwarg in newer SDK)
        model = kwargs.get("_ambertrace_model") or kwargs.get("model", "unknown")

        # Extract and normalize contents to messages
        contents = kwargs.get("contents")
        messages = self._normalize_contents(contents)

        # Extract parameters (exclude sensitive and known keys)
        parameters = {k: v for k, v in kwargs.items() if k not in _EXCLUDED_PARAM_KEYS}

        return {
            "model": model,
            "messages": messages,
            "parameters": parameters,
        }

    def _normalize_contents(self, contents: Any) -> List[Dict[str, str]]:
        """Convert Gemini contents to unified messages format.

        Handles:
        - None -> empty list
        - str -> single user message
        - list of strings -> user messages
        - list of Content objects (with role and parts)
        - list of Part objects (with text)
        - list of dicts with role/parts

        Args:
            contents: Gemini contents parameter

        Returns:
            List of {role, content} dictionaries
        """
        messages: List[Dict[str, str]] = []

        if contents is None:
            return messages

        if isinstance(contents, str):
            messages.append({"role": "user", "content": contents})
            return messages

        if isinstance(contents, list):
            for item in contents:
                if isinstance(item, str):
                    messages.append({"role": "user", "content": item})
                elif isinstance(item, dict):
                    role = item.get("role", "user")
                    parts = item.get("parts", [])
                    text = self._extract_text_from_parts(parts)
                    messages.append({"role": str(role), "content": text})
                elif hasattr(item, "role") and hasattr(item, "parts"):
                    # Content object
                    role = getattr(item, "role", "user")
                    parts = getattr(item, "parts", [])
                    text = self._extract_text_from_parts(parts)
                    messages.append({"role": str(role), "content": text})
                elif hasattr(item, "text"):
                    # Single Part object
                    messages.append({"role": "user", "content": str(getattr(item, "text", ""))})
            return messages

        # Fallback: try to convert to string
        messages.append({"role": "user", "content": str(contents)})
        return messages

    def _extract_text_from_parts(self, parts: Any) -> str:
        """Extract text content from Gemini Part objects.

        Args:
            parts: List of Part objects, dicts, or strings

        Returns:
            Concatenated text content
        """
        text_parts = []
        if not isinstance(parts, (list, tuple)):
            if isinstance(parts, str):
                return parts
            if hasattr(parts, "text"):
                return str(getattr(parts, "text", ""))
            return str(parts)

        for part in parts:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict):
                if "text" in part:
                    text_parts.append(str(part["text"]))
            elif hasattr(part, "text"):
                text_val = getattr(part, "text", None)
                if text_val is not None:
                    text_parts.append(str(text_val))

        return " ".join(text_parts)

    def _build_response_data(self, response: Any) -> Dict[str, Any]:
        """Build response data dict from Gemini response object.

        Normalizes Gemini response format to match the unified structure.

        Args:
            response: Gemini GenerateContentResponse object

        Returns:
            Normalized response data dict
        """
        # Extract response ID if available
        response_id = getattr(response, "response_id", None) or "unknown"

        # Extract model from response if available
        model = getattr(response, "model", None) or "unknown"

        # Extract candidates
        candidates = getattr(response, "candidates", []) or []
        choices = []

        for i, candidate in enumerate(candidates):
            # Extract content text from candidate
            content = getattr(candidate, "content", None)
            text = ""
            if content:
                parts = getattr(content, "parts", [])
                text = self._extract_text_from_parts(parts)

            # Extract and normalize finish reason
            raw_finish_reason = getattr(candidate, "finish_reason", None)
            finish_reason = self._normalize_finish_reason(raw_finish_reason)

            choices.append(
                {
                    "index": i,
                    "message": {
                        "role": "assistant",
                        "content": text,
                    },
                    "finish_reason": finish_reason,
                }
            )

        # If no candidates but response has .text, use that
        if not choices:
            text = ""
            try:
                text_attr = getattr(response, "text", None)
                if callable(text_attr):
                    text = text_attr()
                elif text_attr is not None:
                    text = str(text_attr)
            except Exception:
                pass

            if text:
                choices.append(
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": text},
                        "finish_reason": "stop",
                    }
                )

        # Extract usage metadata
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata:
            prompt_tokens = getattr(usage_metadata, "prompt_token_count", 0) or 0
            completion_tokens = getattr(usage_metadata, "candidates_token_count", 0) or 0
            total_tokens = getattr(
                usage_metadata, "total_token_count", prompt_tokens + completion_tokens
            ) or (prompt_tokens + completion_tokens)
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
        else:
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        return {
            "id": response_id,
            "model": model,
            "choices": choices,
            "usage": usage,
        }

    def _normalize_finish_reason(self, raw_reason: Any) -> str:
        """Normalize Gemini finish reason to unified format.

        Handles both string enum names and integer enum values.

        Args:
            raw_reason: Raw finish reason from Gemini response

        Returns:
            Normalized finish reason string
        """
        if raw_reason is None:
            return "stop"

        # Try direct lookup (handles strings and ints)
        result = _FINISH_REASON_MAP.get(raw_reason)
        if result:
            return result

        # Try string conversion (handles enum objects)
        try:
            str_reason = str(raw_reason)
            result = _FINISH_REASON_MAP.get(str_reason)
            if result:
                return result
            # Try the .name attribute for enum objects
            if hasattr(raw_reason, "name"):
                result = _FINISH_REASON_MAP.get(raw_reason.name)
                if result:
                    return result
            # Try the .value attribute for enum objects
            if hasattr(raw_reason, "value"):
                result = _FINISH_REASON_MAP.get(raw_reason.value)
                if result:
                    return result
        except Exception:
            pass

        return str(raw_reason)

    def _build_error_data(self, error: Exception) -> Dict[str, Any]:
        """Build error data dict from exception.

        Args:
            error: Exception that occurred during API call

        Returns:
            Normalized error data dict
        """
        error_type = type(error).__name__
        error_message = str(error)
        error_code = None

        # Try to extract error details
        if hasattr(error, "status_code"):
            error_code = str(error.status_code)
        elif hasattr(error, "code"):
            error_code = str(error.code)
        elif hasattr(error, "reason"):
            error_code = str(error.reason)
        elif hasattr(error, "type"):
            error_code = str(error.type)

        return {
            "type": error_type,
            "message": error_message,
            "code": error_code,
        }

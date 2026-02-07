"""Trace collection and serialization for OpenAI."""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ambertrace.config import get_config
from ambertrace.providers.base import BaseCollector

logger = logging.getLogger(__name__)


class OpenAICollector(BaseCollector):
    """Collects and builds trace objects from OpenAI API calls.

    This class is responsible for:
    - Extracting data from OpenAI request/response objects
    - Normalizing to unified dict format
    - Calling build_trace() for dataclass creation and serialization
    - Never raising exceptions (defensive error handling)
    """

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "openai"

    def collect_trace(
        self,
        trace_id: str,
        start_time: float,
        request_kwargs: Dict[str, Any],
        response: Optional[Any] = None,
        error: Optional[Exception] = None,
    ) -> Optional[Dict[str, Any]]:
        """Collect and serialize a trace from an OpenAI API call.

        Args:
            trace_id: Unique trace identifier (UUID)
            start_time: Start timestamp from time.time()
            request_kwargs: Kwargs passed to OpenAI API call
            response: OpenAI response object (if successful)
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
                provider="openai",
                method="chat.completions.create",
                duration_ms=duration_ms,
                request_data=request_data,
                response_data=response_data,
                error_data=error_data,
                environment=environment,
            )

            if trace_dict:
                logger.debug(f"Collected OpenAI trace {trace_id} (duration: {duration_ms:.2f}ms)")

            return trace_dict

        except Exception as e:
            # Never raise exceptions - log and return None
            logger.error(f"Failed to collect OpenAI trace {trace_id}: {e}", exc_info=True)
            return None

    def _build_request_data(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Build request data dict from OpenAI API call kwargs.

        Args:
            kwargs: Keyword arguments passed to OpenAI API

        Returns:
            Normalized request data dict
        """
        # Extract model
        model = kwargs.get("model", "unknown")

        # Extract messages
        raw_messages = kwargs.get("messages", [])
        messages = []
        for msg in raw_messages:
            # Handle both dict and object formats
            if isinstance(msg, dict):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
            else:
                role = getattr(msg, "role", "unknown")
                content = getattr(msg, "content", "")

            messages.append({"role": role, "content": str(content)})

        # Extract parameters (temperature, max_tokens, etc.)
        # Exclude model and messages from parameters
        excluded_keys = {"model", "messages"}
        parameters = {k: v for k, v in kwargs.items() if k not in excluded_keys}

        return {
            "model": model,
            "messages": messages,
            "parameters": parameters,
        }

    def _build_response_data(self, response: Any) -> Dict[str, Any]:
        """Build response data dict from OpenAI response object.

        Args:
            response: OpenAI ChatCompletion response object

        Returns:
            Normalized response data dict
        """
        # Extract response ID
        response_id = getattr(response, "id", "unknown")

        # Extract model
        model = getattr(response, "model", "unknown")

        # Extract choices
        raw_choices = getattr(response, "choices", [])
        choices = []
        for choice in raw_choices:
            index = getattr(choice, "index", 0)
            finish_reason = getattr(choice, "finish_reason", "unknown")

            # Extract message
            msg = getattr(choice, "message", None)
            if msg:
                role = getattr(msg, "role", "assistant")
                content = getattr(msg, "content", "")
                message = {"role": role, "content": str(content) if content else ""}
            else:
                message = {"role": "assistant", "content": ""}

            choices.append({
                "index": index,
                "message": message,
                "finish_reason": finish_reason,
            })

        # Extract usage
        usage_obj = getattr(response, "usage", None)
        if usage_obj:
            usage = {
                "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0),
                "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
                "total_tokens": getattr(usage_obj, "total_tokens", 0),
            }
        else:
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        return {
            "id": response_id,
            "model": model,
            "choices": choices,
            "usage": usage,
        }

    def _build_error_data(self, error: Exception) -> Dict[str, Any]:
        """Build error data dict from exception.

        Args:
            error: Exception that occurred during API call

        Returns:
            Normalized error data dict
        """
        error_type = type(error).__name__
        error_message = str(error)

        # Try to extract OpenAI error code if available
        error_code = None
        if hasattr(error, "code"):
            error_code = str(error.code)
        elif hasattr(error, "status_code"):
            error_code = str(error.status_code)

        return {
            "type": error_type,
            "message": error_message,
            "code": error_code,
        }

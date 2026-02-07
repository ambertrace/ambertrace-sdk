"""Trace collection and serialization for Anthropic Claude."""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ambertrace.config import get_config
from ambertrace.providers.base import BaseCollector

logger = logging.getLogger(__name__)


class AnthropicCollector(BaseCollector):
    """Collects and builds trace objects from Anthropic Claude API calls.

    This class is responsible for:
    - Extracting data from Anthropic request/response objects
    - Normalizing to unified dict format
    - Calling build_trace() for dataclass creation and serialization
    - Never raising exceptions (defensive error handling)
    """

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "anthropic"

    def collect_trace(
        self,
        trace_id: str,
        start_time: float,
        request_kwargs: Dict[str, Any],
        response: Optional[Any] = None,
        error: Optional[Exception] = None,
    ) -> Optional[Dict[str, Any]]:
        """Collect and serialize a trace from an Anthropic API call.

        Args:
            trace_id: Unique trace identifier (UUID)
            start_time: Start timestamp from time.time()
            request_kwargs: Kwargs passed to Anthropic API call
            response: Anthropic response object (if successful)
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
                provider="anthropic",
                method="messages.create",
                duration_ms=duration_ms,
                request_data=request_data,
                response_data=response_data,
                error_data=error_data,
                environment=environment,
            )

            if trace_dict:
                logger.debug(f"Collected Anthropic trace {trace_id} (duration: {duration_ms:.2f}ms)")

            return trace_dict

        except Exception as e:
            # Never raise exceptions - log and return None
            logger.error(f"Failed to collect Anthropic trace {trace_id}: {e}", exc_info=True)
            return None

    def _build_request_data(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Build request data dict from Anthropic API call kwargs.

        Args:
            kwargs: Keyword arguments passed to Anthropic API

        Returns:
            Normalized request data dict
        """
        # Extract model
        model = kwargs.get("model", "unknown")

        # Extract messages
        raw_messages = kwargs.get("messages", [])
        messages = []

        # Anthropic has a separate 'system' parameter
        # Prepend it as a system message for consistency with OpenAI format
        system = kwargs.get("system")
        if system:
            messages.append({"role": "system", "content": str(system)})

        # Process messages
        for msg in raw_messages:
            if isinstance(msg, dict):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
            else:
                role = getattr(msg, "role", "unknown")
                content = getattr(msg, "content", "")

            # Anthropic content can be a string or list of content blocks
            if isinstance(content, list):
                # Join text blocks into single string
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                    elif hasattr(block, "type") and block.type == "text":
                        text_parts.append(getattr(block, "text", ""))
                content = " ".join(text_parts)

            messages.append({"role": role, "content": str(content)})

        # Extract parameters
        # Exclude model, messages, and system from parameters
        excluded_keys = {"model", "messages", "system"}
        parameters = {k: v for k, v in kwargs.items() if k not in excluded_keys}

        return {
            "model": model,
            "messages": messages,
            "parameters": parameters,
        }

    def _build_response_data(self, response: Any) -> Dict[str, Any]:
        """Build response data dict from Anthropic Message object.

        Normalizes Anthropic response format to match the unified structure.

        Args:
            response: Anthropic Message response object

        Returns:
            Normalized response data dict
        """
        # Extract response ID
        response_id = getattr(response, "id", "unknown")

        # Extract model
        model = getattr(response, "model", "unknown")

        # Extract content blocks
        content_blocks = getattr(response, "content", [])
        assistant_message = ""

        # Anthropic returns list of ContentBlocks
        for block in content_blocks:
            if hasattr(block, "type") and block.type == "text":
                assistant_message += getattr(block, "text", "")
            elif isinstance(block, dict) and block.get("type") == "text":
                assistant_message += block.get("text", "")

        # Build choices array (Anthropic always has 1 choice)
        # Map Anthropic's stop_reason to OpenAI's finish_reason
        stop_reason = getattr(response, "stop_reason", "unknown")
        finish_reason_map = {
            "end_turn": "stop",
            "max_tokens": "length",
            "stop_sequence": "stop",
        }
        finish_reason = finish_reason_map.get(stop_reason, stop_reason)

        choices = [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": assistant_message,
                },
                "finish_reason": finish_reason,
            }
        ]

        # Extract usage and normalize to OpenAI format
        usage_obj = getattr(response, "usage", None)
        if usage_obj:
            input_tokens = getattr(usage_obj, "input_tokens", 0)
            output_tokens = getattr(usage_obj, "output_tokens", 0)
            # Map Anthropic naming to OpenAI naming
            usage = {
                "prompt_tokens": input_tokens,  # input_tokens → prompt_tokens
                "completion_tokens": output_tokens,  # output_tokens → completion_tokens
                "total_tokens": input_tokens + output_tokens,  # Calculate total
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
        error_code = None

        # Try to extract Anthropic error details
        if hasattr(error, "status_code"):
            error_code = str(error.status_code)
        elif hasattr(error, "code"):
            error_code = str(error.code)
        elif hasattr(error, "type"):
            # Anthropic errors have a 'type' field
            error_code = str(error.type)

        return {
            "type": error_type,
            "message": error_message,
            "code": error_code,
        }

"""Configuration management for AmberTrace SDK."""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class Config:
    """Configuration for AmberTrace SDK.

    Loads configuration from parameters or environment variables.
    Environment variables serve as fallbacks when parameters are not provided.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        environment: Optional[str] = None,
        debug: Optional[bool] = None,
        timeout: Optional[float] = None,
        enabled: Optional[bool] = None,
    ):
        """Initialize configuration.

        Args:
            api_key: AmberTrace API key (or set AMBERTRACE_API_KEY env var)
            base_url: Backend API URL (default: https://api.ambertrace.io)
            environment: Environment tag (e.g., "production", "staging")
            debug: Enable debug logging (default: False)
            timeout: Network timeout in seconds (default: 5.0)
            enabled: Enable/disable tracing (default: True)

        Raises:
            ValueError: If no API key is provided via parameter or environment variable
        """
        # API key (required)
        self.api_key = api_key or os.getenv("AMBERTRACE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "AmberTrace API key is required. "
                "Provide via api_key parameter or AMBERTRACE_API_KEY environment variable."
            )

        # Base URL (optional, with default)
        self.base_url = (
            base_url
            or os.getenv("AMBERTRACE_BASE_URL")
            or "https://api.ambertrace.io"
        )
        # Ensure base_url doesn't have trailing slash
        self.base_url = self.base_url.rstrip("/")

        # Environment tag (optional)
        self.environment = environment or os.getenv("AMBERTRACE_ENV")

        # Debug mode (optional, default: False)
        if debug is not None:
            self.debug = debug
        else:
            debug_env = os.getenv("AMBERTRACE_DEBUG", "").lower()
            self.debug = debug_env in ("true", "1", "yes")

        # Timeout (optional, default: 5.0 seconds)
        if timeout is not None:
            self.timeout = timeout
        else:
            timeout_env = os.getenv("AMBERTRACE_TIMEOUT")
            self.timeout = float(timeout_env) if timeout_env else 5.0

        # Enabled flag (optional, default: True)
        if enabled is not None:
            self.enabled = enabled
        else:
            enabled_env = os.getenv("AMBERTRACE_ENABLED", "").lower()
            # Default to enabled unless explicitly disabled
            self.enabled = enabled_env not in ("false", "0", "no")

        # Configure logging based on debug mode
        self._configure_logging()

    def _configure_logging(self) -> None:
        """Configure logging level based on debug mode."""
        log_level = logging.DEBUG if self.debug else logging.WARNING

        # Configure the ambertrace logger
        ambertrace_logger = logging.getLogger("ambertrace")
        ambertrace_logger.setLevel(log_level)

        # Add handler if none exists
        if not ambertrace_logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(log_level)
            formatter = logging.Formatter("[ambertrace] %(levelname)s: %(message)s")
            handler.setFormatter(formatter)
            ambertrace_logger.addHandler(handler)

        # Prevent propagation to root logger
        ambertrace_logger.propagate = False

    @property
    def traces_endpoint(self) -> str:
        """Get the full traces endpoint URL."""
        return f"{self.base_url}/api/traces/ingest"

    def __repr__(self) -> str:
        """String representation (masks API key)."""
        masked_key = f"{self.api_key[:8]}..." if len(self.api_key) > 8 else "***"
        return (
            f"Config(api_key={masked_key}, base_url={self.base_url}, "
            f"environment={self.environment}, debug={self.debug}, "
            f"timeout={self.timeout}, enabled={self.enabled})"
        )


# Global configuration instance
_global_config: Optional[Config] = None


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _global_config
    _global_config = config


def get_config() -> Optional[Config]:
    """Get the global configuration instance."""
    return _global_config


def is_configured() -> bool:
    """Check if configuration has been initialized."""
    return _global_config is not None

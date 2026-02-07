"""Provider registry for managing multiple LLM providers.

The registry maintains a collection of registered providers and handles
patching/unpatching all of them at once.
"""

import logging
from typing import Dict, List, Optional

from ambertrace.providers.base import BaseCollector, BaseInterceptor

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry for managing multiple LLM provider interceptors and collectors.

    The registry acts as a central coordinator for all registered providers,
    allowing AmberTrace to support multiple LLM SDKs simultaneously.
    """

    def __init__(self) -> None:
        """Initialize the provider registry."""
        self._interceptors: Dict[str, BaseInterceptor] = {}
        self._collectors: Dict[str, BaseCollector] = {}

    def register_provider(
        self,
        name: str,
        interceptor: BaseInterceptor,
        collector: BaseCollector,
    ) -> None:
        """Register a provider's interceptor and collector.

        Args:
            name: Provider name (e.g., 'openai', 'anthropic')
            interceptor: Provider's interceptor implementation
            collector: Provider's collector implementation

        Example:
            >>> registry = ProviderRegistry()
            >>> registry.register_provider(
            ...     'openai',
            ...     OpenAIInterceptor(),
            ...     OpenAICollector()
            ... )
        """
        self._interceptors[name] = interceptor
        self._collectors[name] = collector
        logger.debug(f"Registered provider: {name}")

    def unregister_provider(self, name: str) -> None:
        """Unregister a provider.

        Args:
            name: Provider name to unregister
        """
        if name in self._interceptors:
            # Unpatch before unregistering
            interceptor = self._interceptors[name]
            if interceptor.is_patched():
                interceptor.unpatch()

            del self._interceptors[name]
            del self._collectors[name]
            logger.debug(f"Unregistered provider: {name}")

    def patch_all(self) -> None:
        """Apply patches for all registered providers.

        This method calls patch() on all registered interceptors.
        Errors in individual providers are caught and logged but don't
        prevent other providers from being patched.
        """
        if not self._interceptors:
            logger.warning("No providers registered, nothing to patch")
            return

        patched_count = 0
        for name, interceptor in self._interceptors.items():
            try:
                interceptor.patch()
                if interceptor.is_patched():
                    patched_count += 1
                    logger.debug(f"Patched provider: {name}")
            except Exception as e:
                logger.error(f"Failed to patch provider '{name}': {e}", exc_info=True)

        if patched_count > 0:
            logger.info(f"Successfully patched {patched_count} provider(s)")
        else:
            logger.warning("No providers were successfully patched")

    def unpatch_all(self) -> None:
        """Remove patches for all registered providers.

        This method calls unpatch() on all registered interceptors.
        Errors are caught and logged but don't prevent other providers
        from being unpatched.
        """
        if not self._interceptors:
            logger.debug("No providers registered, nothing to unpatch")
            return

        for name, interceptor in self._interceptors.items():
            try:
                interceptor.unpatch()
                logger.debug(f"Unpatched provider: {name}")
            except Exception as e:
                logger.error(f"Failed to unpatch provider '{name}': {e}", exc_info=True)

        logger.info("All providers unpatched")

    def get_interceptor(self, provider: str) -> Optional[BaseInterceptor]:
        """Get the interceptor for a specific provider.

        Args:
            provider: Provider name (e.g., 'openai', 'anthropic')

        Returns:
            Provider's interceptor, or None if not registered
        """
        return self._interceptors.get(provider)

    def get_collector(self, provider: str) -> Optional[BaseCollector]:
        """Get the collector for a specific provider.

        Args:
            provider: Provider name (e.g., 'openai', 'anthropic')

        Returns:
            Provider's collector, or None if not registered
        """
        return self._collectors.get(provider)

    def is_patched(self) -> bool:
        """Check if any provider is currently patched.

        Returns:
            True if at least one provider is patched, False otherwise
        """
        return any(interceptor.is_patched() for interceptor in self._interceptors.values())

    def get_registered_providers(self) -> List[str]:
        """Get list of all registered provider names.

        Returns:
            List of provider names (e.g., ['openai', 'anthropic'])
        """
        return list(self._interceptors.keys())

    def get_patched_providers(self) -> List[str]:
        """Get list of currently patched provider names.

        Returns:
            List of provider names that are currently patched
        """
        return [
            name
            for name, interceptor in self._interceptors.items()
            if interceptor.is_patched()
        ]

    def __repr__(self) -> str:
        """String representation of the registry."""
        registered = self.get_registered_providers()
        patched = self.get_patched_providers()
        return (
            f"ProviderRegistry(registered={registered}, patched={patched})"
        )


# Global registry instance
_global_registry: Optional[ProviderRegistry] = None


def get_registry() -> Optional[ProviderRegistry]:
    """Get the global provider registry instance.

    Returns:
        Global registry instance, or None if not initialized
    """
    return _global_registry


def set_registry(registry: ProviderRegistry) -> None:
    """Set the global provider registry instance.

    Args:
        registry: ProviderRegistry instance to set as global
    """
    global _global_registry
    _global_registry = registry


def clear_registry() -> None:
    """Clear the global provider registry."""
    global _global_registry
    _global_registry = None

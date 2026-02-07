"""Provider abstraction for multi-LLM support."""

from ambertrace.providers.base import BaseCollector, BaseInterceptor
from ambertrace.providers.registry import ProviderRegistry, get_registry, set_registry

__all__ = [
    "BaseInterceptor",
    "BaseCollector",
    "ProviderRegistry",
    "get_registry",
    "set_registry",
]

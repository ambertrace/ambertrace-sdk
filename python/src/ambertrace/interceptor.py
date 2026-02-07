"""DEPRECATED: Backward compatibility shim for interceptor.

This module is deprecated. Use ambertrace.providers.openai.interceptor instead.
Kept for backward compatibility with existing code.
"""

from typing import Optional

# Import from new location
from ambertrace.providers.openai.interceptor import OpenAIInterceptor

# For backward compatibility, alias to old name
Interceptor = OpenAIInterceptor

# Global interceptor instance (deprecated)
_global_interceptor: Optional[Interceptor] = None


def get_interceptor() -> Optional[Interceptor]:
    """Get the global interceptor instance.

    DEPRECATED: Use ambertrace.providers.registry instead.
    """
    return _global_interceptor


def set_interceptor(interceptor: Interceptor) -> None:
    """Set the global interceptor instance.

    DEPRECATED: Use ambertrace.providers.registry instead.
    """
    global _global_interceptor
    _global_interceptor = interceptor

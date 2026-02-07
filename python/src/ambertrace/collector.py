"""DEPRECATED: Backward compatibility shim for collector.

This module is deprecated. Use ambertrace.providers.openai.collector instead.
Kept for backward compatibility with existing code.
"""

# Import from new location
from ambertrace.providers.openai.collector import OpenAICollector

# For backward compatibility, alias to old name
TraceCollector = OpenAICollector

# AmberTrace Python SDK

Lightweight, zero-code LLM observability for Python. Trace every API call to OpenAI, Anthropic, and Google automatically.

## Installation

```bash
# Core SDK
pip install ambertrace

# With specific provider support
pip install ambertrace[openai]
pip install ambertrace[anthropic]
pip install ambertrace[gemini]

# All providers
pip install ambertrace[all]
```

**Requirements:** Python 3.8+

## Quick Start

```python
import ambertrace
from openai import OpenAI

# Initialize once at startup
ambertrace.init(api_key="at_...")

# Use your LLM SDK as normal — tracing happens automatically
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Flush before exit
ambertrace.flush()
```

## Supported Providers

| Provider | Models | SDK |
|----------|--------|-----|
| **OpenAI** | GPT-5, GPT-4, GPT-4o, GPT-4o-mini, o1, o3 | `openai>=1.0.0` |
| **Anthropic** | Claude Opus 4.5/4.6, Sonnet 4.5, Haiku | `anthropic>=0.18.0` |
| **Google** | Gemini Pro, Flash, 2.0, Gemma | `google-generativeai>=0.3.0` |

## Async Support

```python
import asyncio
import openai
import ambertrace

async def main():
    ambertrace.init(api_key="at_...")
    client = openai.AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    await ambertrace.flush_async()

asyncio.run(main())
```

## Configuration

```python
ambertrace.init(
    api_key="at_...",            # Required (or AMBERTRACE_API_KEY env var)
    environment="production",     # Environment tag for filtering
    debug=False,                  # Enable debug logging
    timeout=5.0,                  # Network timeout in seconds
    enabled=True,                 # Enable/disable tracing
)
```

## API Reference

- `ambertrace.init()` — Initialize SDK and start tracing
- `ambertrace.enable()` / `ambertrace.disable()` — Toggle tracing at runtime
- `ambertrace.is_enabled()` — Check if tracing is active
- `ambertrace.flush()` — Block until pending traces are sent
- `ambertrace.flush_async()` — Async version of flush
- `ambertrace.shutdown()` — Flush, disable, and clean up

## Links

- [Documentation](https://docs.ambertrace.dev)
- [Portal](https://ambertrace.dev/dashboard)
- [GitHub](https://github.com/ambertrace/ambertrace-sdk)

## License

[Apache 2.0](https://github.com/ambertrace/ambertrace-sdk/blob/main/LICENSE)

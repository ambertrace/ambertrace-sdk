# AmberTrace SDK

Lightweight, zero-code LLM observability. Trace every API call to OpenAI, Anthropic, and Google Gemini — capturing requests, responses, token usage, latency, and errors — with two lines of code.

## Supported Providers

| Provider | Models | Python SDK | Node.js SDK |
|----------|--------|------------|-------------|
| **OpenAI** | GPT-5, GPT-4, GPT-4o, GPT-4o-mini, o1, o3 | `openai` | `openai` |
| **Anthropic** | Claude Opus 4.5, Sonnet 4.5, Haiku | `anthropic` | `@anthropic-ai/sdk` |
| **Google Gemini** | Gemini Pro, Flash, 2.0 | `google-generativeai`, `google-genai` | `@google/generative-ai` |

## Quick Start

### Python

```bash
pip install ambertrace
```

```python
import ambertrace
from openai import OpenAI

ambertrace.init(api_key="at_...")

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)

ambertrace.flush()
```

### TypeScript / Node.js

```bash
npm install @ambertrace/node
```

```typescript
import ambertrace from '@ambertrace/node';
import OpenAI from 'openai';

ambertrace.init({ apiKey: 'at_...' });

const client = new OpenAI();
const response = await client.chat.completions.create({
  model: 'gpt-4',
  messages: [{ role: 'user', content: 'Hello!' }]
});

await ambertrace.flush();
```

## How It Works

1. **Install the SDK** — `pip install ambertrace` or `npm install @ambertrace/node`
2. **Call `init()` at startup** — the SDK patches your LLM clients transparently
3. **Use your LLM SDKs normally** — every call is traced automatically
4. **View traces in the portal** — see requests, responses, tokens, latency, and errors

## Features

- **Zero-code integration** — no decorators, wrappers, or middleware
- **Multi-provider** — OpenAI, Anthropic, and Gemini from a single SDK
- **Async support** — works with both sync and async clients
- **Non-blocking** — traces are sent in background threads
- **Never breaks your code** — all tracing errors are caught internally

## SDK Documentation

- [Python SDK](python/) — Python 3.8+, sync and async support
- [TypeScript SDK](typescript/) — Node.js 16+, ESM and CommonJS

## Links

- [Website](https://ambertrace.dev)
- [Documentation](https://docs.ambertrace.dev)
- [Portal](https://app.ambertrace.dev)
- Contact: hello@ambertrace.dev

## License

[Apache 2.0](LICENSE)

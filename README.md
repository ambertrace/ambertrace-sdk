# AmberTrace SDK

Lightweight, zero-code LLM observability tool. Trace every API call to OpenAI, Anthropic, and Google — capturing requests, responses, token usage, latency, and errors — with two lines of code.

## Supported Providers

| Provider | Models | Python SDK | Node.js SDK | Java SDK |
|----------|--------|------------|-------------|----------|
| **OpenAI** | GPT-5, GPT-4, GPT-4o, GPT-4o-mini, o1, o3 | `openai` | `openai` | `com.openai:openai-java` |
| **Anthropic** | Claude Opus 4.5/4.6, Sonnet 4.5, Haiku | `anthropic` | `@anthropic-ai/sdk` | `com.anthropic:anthropic-java` |
| **Google** | Gemini Pro, Flash, 2.0, Gemma | `google-generativeai`, `google-genai` | `@google/generative-ai` | `com.google.genai:google-genai` |

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

### Java

```xml
<dependency>
    <groupId>dev.ambertrace</groupId>
    <artifactId>ambertrace-java</artifactId>
    <version>0.1.0</version>
</dependency>
```

```java
import dev.ambertrace.AmberTrace;
import com.openai.client.OpenAIClient;
import com.openai.client.okhttp.OpenAIOkHttpClient;
import com.openai.models.ChatModel;
import com.openai.models.chat.completions.*;

AmberTrace.init("at_...");

OpenAIClient client = AmberTrace.wrap(
    OpenAIOkHttpClient.builder().apiKey("sk-...").build()
);
ChatCompletion completion = client.chat().completions().create(
    ChatCompletionCreateParams.builder()
        .model(ChatModel.GPT_4O)
        .addUserMessage("Hello!")
        .build()
);

AmberTrace.flush();
```

## How It Works

1. **Install the SDK** — `pip install ambertrace`, `npm install @ambertrace/node`, or add `dev.ambertrace:ambertrace-java` to Maven
2. **Call `init()` at startup** — the SDK patches your LLM clients transparently (Python/TS) or wraps them (Java)
3. **Use your LLM SDKs normally** — every call is traced automatically
4. **View traces in the portal** — see requests, responses, tokens, latency, and errors at https://www.ambertrace.dev/dashboard 

## Features

- **Zero-code integration** — no decorators, wrappers, or middleware
- **Multi-provider** — OpenAI, Anthropic, and Google from a single SDK
- **Async support** — works with both sync and async clients
- **Non-blocking** — traces are sent in background threads
- **Never breaks your code** — all tracing errors are caught internally

## SDK Documentation

- [Python SDK](python/) — Python 3.8+, sync and async support
- [TypeScript SDK](typescript/) — Node.js 16+, ESM and CommonJS
- [Java SDK](java/) — Java 11+, sync and async support

## Links

- [Website](https://ambertrace.dev)
- [Documentation](https://docs.ambertrace.dev)
- [Portal](https://ambertrace.dev/dashboard)
- Contact: hello@ambertrace.dev

## License

[Apache 2.0](LICENSE)

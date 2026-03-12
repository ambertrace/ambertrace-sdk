# AmberTrace Java SDK

LLM observability for Java. Trace every API call to OpenAI, Anthropic, and Google Gemini — capturing requests, responses, token usage, latency, and errors.

## Installation

### Maven

```xml
<dependency>
    <groupId>dev.ambertrace</groupId>
    <artifactId>ambertrace-java</artifactId>
    <version>0.1.0</version>
</dependency>
```

### Gradle

```groovy
implementation("dev.ambertrace:ambertrace-java:0.1.0")
```

**Requirements:** Java 11+

## Quick Start

### OpenAI

```java
import dev.ambertrace.AmberTrace;
import com.openai.client.OpenAIClient;
import com.openai.client.okhttp.OpenAIOkHttpClient;
import com.openai.models.ChatModel;
import com.openai.models.chat.completions.*;

// Initialize tracing
AmberTrace.init("at_your_api_key");

// Wrap your client
OpenAIClient client = AmberTrace.wrap(
    OpenAIOkHttpClient.builder().apiKey("sk-...").build()
);

// Use normally — calls are traced automatically
ChatCompletion completion = client.chat().completions().create(
    ChatCompletionCreateParams.builder()
        .model(ChatModel.GPT_4O)
        .addUserMessage("Hello!")
        .build()
);

// Flush before exit
AmberTrace.flush();
```

### Anthropic

```java
import dev.ambertrace.AmberTrace;
import com.anthropic.client.AnthropicClient;
import com.anthropic.client.okhttp.AnthropicOkHttpClient;
import com.anthropic.models.messages.*;

AmberTrace.init("at_your_api_key");

AnthropicClient client = AmberTrace.wrap(
    AnthropicOkHttpClient.builder().apiKey("sk-ant-...").build()
);

Message message = client.messages().create(
    MessageCreateParams.builder()
        .model(Model.CLAUDE_SONNET_4_5_20250929)
        .maxTokens(1024)
        .addUserMessage("Hello, Claude!")
        .build()
);

AmberTrace.flush();
```

### Google Gemini

```java
import dev.ambertrace.AmberTrace;
import com.google.genai.Client;
import com.google.genai.types.GenerateContentResponse;

AmberTrace.init("at_your_api_key");

Client gemini = AmberTrace.wrap(
    Client.builder().apiKey("your-google-api-key").build()
);

GenerateContentResponse response = gemini.models.generateContent(
    "gemini-2.0-flash", "What is your name?", null
);

AmberTrace.flush();
```

## Configuration

```java
import dev.ambertrace.AmberTrace;
import dev.ambertrace.Config;

// Full configuration
AmberTrace.init(Config.builder()
    .apiKey("at_your_api_key")        // Required (or set AMBERTRACE_API_KEY env var)
    .environment("production")         // Optional: tag traces with environment
    .debug(true)                       // Optional: enable debug logging
    .timeoutMs(10000)                  // Optional: HTTP timeout (default: 5000ms)
    .enabled(true)                     // Optional: enable/disable (default: true)
    .build()
);

// Or use environment variables only
AmberTrace.init();
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AMBERTRACE_API_KEY` | API key | (required) |
| `AMBERTRACE_BASE_URL` | Backend URL | `https://api.ambertrace.dev` |
| `AMBERTRACE_ENV` | Environment tag | (none) |
| `AMBERTRACE_DEBUG` | Debug logging | `false` |
| `AMBERTRACE_ENABLED` | Enable tracing | `true` |

## API Reference

| Method | Description |
|--------|-------------|
| `AmberTrace.init(apiKey)` | Initialize with API key |
| `AmberTrace.init(config)` | Initialize with full config |
| `AmberTrace.init()` | Initialize from env vars |
| `AmberTrace.wrap(client)` | Wrap a provider client for tracing |
| `AmberTrace.flush()` | Wait for pending traces (5s timeout) |
| `AmberTrace.flush(timeoutMs)` | Wait for pending traces with custom timeout |
| `AmberTrace.disable()` | Disable tracing |
| `AmberTrace.enable()` | Re-enable tracing |
| `AmberTrace.isEnabled()` | Check if tracing is active |
| `AmberTrace.shutdown()` | Full cleanup: flush + stop transport |
| `AmberTrace.getVersion()` | Get SDK version |

## Provider Compatibility

| Provider | Library | Tested Version | Traced Method | Sync | Async |
|----------|---------|---------------|---------------|------|-------|
| OpenAI | [`com.openai:openai-java`](https://github.com/openai/openai-java) | 4.26.0 | `chat().completions().create()` | ✅ | ✅ |
| Anthropic | [`com.anthropic:anthropic-java`](https://github.com/anthropics/anthropic-sdk-java) | 2.15.0 | `messages().create()` | ✅ | ✅ |
| Google Gemini | [`com.google.genai:google-genai`](https://github.com/googleapis/java-genai) | 1.4.1 | `models.generateContent()` | ✅ | ✅ |

### Captured Data

Each trace includes:

- **Request** — model, messages (role + content), parameters (temperature, top_p, max tokens)
- **Response** — completion text, finish reason, response model
- **Token usage** — prompt, completion, total, cached, and reasoning tokens
- **Metadata** — trace ID, timestamp, duration, provider, environment, SDK version
- **Errors** — exception type, message, HTTP status code (when available)

## How It Works

Unlike Python and TypeScript SDKs which use monkey-patching, the Java SDK uses the **wrapper/decorator pattern**. `AmberTrace.wrap(client)` returns a traced proxy with the same API as the original client. The proxy intercepts API calls to record timing, request/response data, and sends traces to the backend.

Traces are sent asynchronously in background daemon threads and never block your application. All errors in the tracing layer are caught and logged — your LLM calls always work, even if tracing fails.

## License

[Apache 2.0](../LICENSE)

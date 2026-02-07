# AmberTrace TypeScript/Node.js SDK

Official TypeScript/Node.js SDK for tracing LLM calls (OpenAI, Anthropic, Google Gemini) to the AmberTrace observability platform.

## Features

- **Zero-code integration** - Just call `init()` and your LLM calls are automatically traced
- **Multi-provider support** - Works with OpenAI, Anthropic, and Google Gemini SDKs simultaneously
- **Framework-agnostic** - Works with Express, NestJS, Next.js, and any Node.js framework
- **Type-safe** - Full TypeScript support with complete type definitions
- **Dual module support** - Works with both ESM and CommonJS
- **Async-first** - Non-blocking trace delivery never impacts your application performance
- **Silent failures** - Network issues never crash your application
- **Auto-detection** - Automatically detects and instruments installed LLM SDKs

## Installation

```bash
npm install @ambertrace/node
```

Install your preferred LLM SDK(s):

```bash
# For OpenAI support
npm install openai

# For Anthropic support
npm install @anthropic-ai/sdk

# For Google Gemini support (original SDK)
npm install @google/generative-ai

# For Google Gemini support (newer SDK)
npm install @google/genai

# Or all providers
npm install openai @anthropic-ai/sdk @google/generative-ai
```

## Quick Start

```typescript
import ambertrace from '@ambertrace/node';
import OpenAI from 'openai';

// 1. Initialize AmberTrace (one time, at app startup)
ambertrace.init({
  apiKey: process.env.AMBERTRACE_API_KEY,
  environment: 'production',
});

// 2. Use OpenAI as normal - calls are automatically traced!
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const response = await openai.chat.completions.create({
  model: 'gpt-4',
  messages: [{ role: 'user', content: 'Hello!' }],
});

console.log(response.choices[0].message.content);

// 3. Before exiting, flush pending traces
await ambertrace.flush();
```

That's it! Every OpenAI, Anthropic, and Gemini call is now traced to your AmberTrace dashboard.

## Configuration

### Initialization Options

```typescript
ambertrace.init({
  // Required: Your AmberTrace API key
  apiKey: 'your-api-key',

  // Optional: Base URL for AmberTrace API (default: https://api.ambertrace.io)
  baseUrl: 'https://api.ambertrace.io',

  // Optional: Environment name for filtering traces (e.g., "production", "staging")
  environment: 'production',

  // Optional: Enable debug logging (default: false)
  debug: true,

  // Optional: HTTP request timeout in ms (default: 5000)
  timeout: 5000,

  // Optional: Enable/disable tracing (default: true)
  enabled: true,
});
```

### Environment Variables

All configuration can be set via environment variables:

```bash
export AMBERTRACE_API_KEY="your-api-key"
export AMBERTRACE_BASE_URL="https://api.ambertrace.io"
export AMBERTRACE_ENVIRONMENT="production"
export AMBERTRACE_DEBUG="true"
export AMBERTRACE_TIMEOUT="5000"
export AMBERTRACE_ENABLED="true"
```

## API Reference

### `init(options)`

Initialize the SDK and start tracing.

```typescript
ambertrace.init({
  apiKey: 'your-api-key',
  environment: 'production',
});
```

### `enable()`

Enable tracing (applies interception).

```typescript
ambertrace.enable();
```

### `disable()`

Disable tracing (removes interception).

```typescript
ambertrace.disable();
```

### `isEnabled()`

Check if tracing is currently active.

```typescript
if (ambertrace.isEnabled()) {
  console.log('Tracing is active');
}
```

### `flush(timeoutMs?)`

Wait for all pending traces to be sent. Call before process exit.

```typescript
await ambertrace.flush(10000); // Wait up to 10 seconds
```

### `shutdown(timeoutMs?)`

Shutdown the SDK, flush traces, and clean up resources.

```typescript
await ambertrace.shutdown();
```

## Usage Examples

### OpenAI (ESM)

```typescript
import ambertrace from '@ambertrace/node';
import OpenAI from 'openai';

ambertrace.init({ apiKey: process.env.AMBERTRACE_API_KEY });

const openai = new OpenAI();
const response = await openai.chat.completions.create({
  model: 'gpt-4',
  messages: [{ role: 'user', content: 'Explain TypeScript' }],
});

await ambertrace.flush();
```

### Anthropic (ESM)

```typescript
import ambertrace from '@ambertrace/node';
import Anthropic from '@anthropic-ai/sdk';

ambertrace.init({ apiKey: process.env.AMBERTRACE_API_KEY });

const anthropic = new Anthropic();
const response = await anthropic.messages.create({
  model: 'claude-opus-4-5-20251101',
  max_tokens: 100,
  messages: [{ role: 'user', content: 'Hello Claude!' }],
});

await ambertrace.flush();
```

### Google Gemini (ESM)

Using the original `@google/generative-ai` SDK:

```typescript
import ambertrace from '@ambertrace/node';
import { GoogleGenerativeAI } from '@google/generative-ai';

ambertrace.init({ apiKey: process.env.AMBERTRACE_API_KEY });

const genai = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
const model = genai.getGenerativeModel({ model: 'gemini-pro' });

const result = await model.generateContent('Explain TypeScript');
console.log(result.response.text());

await ambertrace.flush();
```

Using the newer `@google/genai` SDK:

```typescript
import ambertrace from '@ambertrace/node';
import { GoogleGenAI } from '@google/genai';

ambertrace.init({ apiKey: process.env.AMBERTRACE_API_KEY });

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY! });
const response = await ai.models.generateContent({
  model: 'gemini-2.0-flash',
  contents: 'Explain TypeScript',
});

console.log(response.text);

await ambertrace.flush();
```

### CommonJS

```javascript
const ambertrace = require('@ambertrace/node').default;
const OpenAI = require('openai');

ambertrace.init({ apiKey: process.env.AMBERTRACE_API_KEY });

const openai = new OpenAI();
// ... use OpenAI as normal
```

### Express.js API

```typescript
import express from 'express';
import ambertrace from '@ambertrace/node';
import OpenAI from 'openai';

// Initialize AmberTrace at app startup
ambertrace.init({ apiKey: process.env.AMBERTRACE_API_KEY });

const app = express();
const openai = new OpenAI();

app.post('/chat', async (req, res) => {
  const response = await openai.chat.completions.create({
    model: 'gpt-4',
    messages: [{ role: 'user', content: req.body.message }],
  });

  res.json({ reply: response.choices[0].message.content });
});

app.listen(3000);

// Graceful shutdown
process.on('SIGTERM', async () => {
  await ambertrace.shutdown();
  process.exit(0);
});
```

### Next.js API Route

```typescript
// app/api/chat/route.ts
import ambertrace from '@ambertrace/node';
import OpenAI from 'openai';

// Initialize once (consider using a singleton)
if (!ambertrace.isEnabled()) {
  ambertrace.init({ apiKey: process.env.AMBERTRACE_API_KEY });
}

const openai = new OpenAI();

export async function POST(request: Request) {
  const { message } = await request.json();

  const response = await openai.chat.completions.create({
    model: 'gpt-4',
    messages: [{ role: 'user', content: message }],
  });

  return Response.json({ reply: response.choices[0].message.content });
}
```

### Multi-Provider (OpenAI + Anthropic + Gemini)

```typescript
import ambertrace from '@ambertrace/node';
import OpenAI from 'openai';
import Anthropic from '@anthropic-ai/sdk';
import { GoogleGenerativeAI } from '@google/generative-ai';

// Single init() traces all providers!
ambertrace.init({ apiKey: process.env.AMBERTRACE_API_KEY });

const openai = new OpenAI();
const anthropic = new Anthropic();
const genai = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);

// All calls are automatically traced
const gptResponse = await openai.chat.completions.create({
  model: 'gpt-4',
  messages: [{ role: 'user', content: 'Hello' }],
});

const claudeResponse = await anthropic.messages.create({
  model: 'claude-opus-4-5-20251101',
  max_tokens: 100,
  messages: [{ role: 'user', content: 'Hello' }],
});

const geminiModel = genai.getGenerativeModel({ model: 'gemini-pro' });
const geminiResponse = await geminiModel.generateContent('Hello');

await ambertrace.flush();
```

## Framework Integration

The SDK works seamlessly with popular Node.js frameworks:

- **Express.js** - Initialize at app startup, traces all LLM calls in routes
- **NestJS** - Initialize in `main.ts`, works with all modules
- **Next.js** - Initialize in API routes or middleware
- **Fastify** - Initialize in startup hook
- **Koa** - Initialize before app.listen()

No framework-specific configuration needed - just call `init()` once!

## Trace Data Format

All traces follow a unified format regardless of provider:

```typescript
interface Trace {
  trace_id: string; // Unique UUID
  timestamp: string; // ISO 8601 UTC
  provider: 'openai' | 'anthropic' | 'gemini'; // Provider identifier
  method: string; // API method name
  duration_ms: number; // Call duration
  request: {
    model: string;
    messages: Array<{ role: string; content: string }>;
    parameters: Record<string, unknown>;
  };
  response?: {
    id: string;
    model: string;
    choices: Array<{
      index: number;
      message: { role: string; content: string };
      finish_reason: string;
    }>;
    usage: {
      prompt_tokens: number;
      completion_tokens: number;
      total_tokens: number;
    };
  };
  error?: {
    type: string;
    message: string;
    code?: string;
  };
  sdk_version: string;
  environment?: string;
}
```

## Error Handling

The SDK follows a **never-fail** philosophy:

- Network errors are logged but never thrown
- Trace collection errors never impact your application
- If the backend is unavailable, traces are silently dropped
- Your LLM calls always succeed/fail based on the provider, not the SDK

Enable `debug: true` to see trace delivery logs:

```typescript
ambertrace.init({
  apiKey: 'your-api-key',
  debug: true, // See trace collection and delivery logs
});
```

## Development

```bash
# Install dependencies
npm install

# Build (ESM + CommonJS + types)
npm run build

# Run tests
npm test

# Lint
npm run lint

# Format
npm run format
```

## TypeScript Support

The SDK is written in TypeScript and includes complete type definitions:

```typescript
import ambertrace, { type Trace, type ConfigOptions } from '@ambertrace/node';

const options: ConfigOptions = {
  apiKey: 'your-api-key',
  environment: 'production',
};

ambertrace.init(options);
```

## License

MIT

## Support

- **Issues**: [GitHub Issues](https://github.com/KirPros/ambertrace/issues)
- **Documentation**: [GitHub README](https://github.com/KirPros/ambertrace#readme)
- **Email**: hello@ambertrace.io

# Changelog

## Python SDK

### v0.1.0

- Initial release
- OpenAI, Anthropic, and Google provider support
- Sync and async tracing
- Background trace delivery via HTTP transport
- Auto-detection of installed provider libraries

## TypeScript SDK

### v0.1.0

- Initial release
- OpenAI, Anthropic, and Google provider support
- ESM and CommonJS module support
- Background trace delivery
- Auto-detection of installed provider libraries

## Java SDK

### v0.1.0

- Initial release
- OpenAI, Anthropic, and Google Gemini provider support
- Wrapper/decorator pattern via `AmberTrace.wrap(client)`
- Background trace delivery via `java.net.http.HttpClient`
- Auto-detection of installed provider libraries via `Class.forName()`
- Java 11+ support (uses built-in HTTP client)

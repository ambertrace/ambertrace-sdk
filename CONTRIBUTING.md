# Contributing to AmberTrace SDK

Thank you for your interest in contributing to AmberTrace SDK.

## Development Setup

### Python SDK

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### TypeScript SDK

```bash
cd typescript
npm install
npm run build
```

### Java SDK

```bash
cd java
mvn compile
```

## Running Tests

### Python

```bash
cd python
pytest
```

### TypeScript

```bash
cd typescript
npm test
```

### Java

```bash
cd java
mvn test
```

## Code Style

### Python

- Formatter: [Black](https://github.com/psf/black) (line length 100)
- Linter: [Ruff](https://github.com/astral-sh/ruff)

```bash
cd python
black src/ tests/
ruff check src/ tests/
```

### TypeScript

- Linter: [ESLint](https://eslint.org/)
- Formatter: [Prettier](https://prettier.io/)

```bash
cd typescript
npm run lint
npm run format
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-change`)
3. Make your changes and add tests
4. Ensure all tests pass
5. Submit a pull request with a clear description of the change

## Adding a New Provider

All SDKs (Python, TypeScript, Java) follow the same architecture:

1. Create a new provider directory under `providers/`
2. Implement a **Collector** (extracts data from provider responses)
3. Implement an **Interceptor** (patches the provider SDK methods)
4. Register the provider in the registry
5. Add tests for both collector and interceptor

See existing providers (OpenAI, Anthropic, Google) as reference implementations.

## License

By contributing, you agree that your contributions will be licensed under the [Apache 2.0 License](LICENSE).

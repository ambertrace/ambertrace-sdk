#!/usr/bin/env python3
"""Multi-provider usage example for AmberTrace SDK.

This example demonstrates:
- Using multiple LLM providers simultaneously
- Single AmberTrace initialization traces all providers
- Comparing responses from different models
- Unified trace format for all providers

Prerequisites:
    pip install ambertrace openai anthropic

Environment variables:
    AMBERTRACE_API_KEY - Your AmberTrace API key
    OPENAI_API_KEY - Your OpenAI API key
    ANTHROPIC_API_KEY - Your Anthropic API key
"""

import os

import anthropic
import openai

import ambertrace


def compare_models(question: str):
    """Ask the same question to different LLM providers."""
    print(f"\n{'='*70}")
    print(f"Question: {question}")
    print(f"{'='*70}\n")

    # Ask GPT-4
    print("GPT-4 (OpenAI):")
    try:
        openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": question}],
            max_tokens=150,
        )
        gpt4_answer = response.choices[0].message.content
        print(f"  {gpt4_answer}")
        print(f"  (Tokens: {response.usage.total_tokens})\n")
    except openai.OpenAIError as e:
        print(f"  Error: {e}\n")

    # Ask Claude Opus
    print("Claude Opus (Anthropic):")
    try:
        anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = anthropic_client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=150,
            messages=[{"role": "user", "content": question}],
        )
        claude_answer = response.content[0].text
        total_tokens = response.usage.input_tokens + response.usage.output_tokens
        print(f"  {claude_answer}")
        print(f"  (Tokens: {total_tokens})\n")
    except anthropic.AnthropicError as e:
        print(f"  Error: {e}\n")

    # Ask GPT-3.5-turbo (faster/cheaper)
    print("GPT-3.5-Turbo (OpenAI):")
    try:
        openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": question}],
            max_tokens=150,
        )
        gpt35_answer = response.choices[0].message.content
        print(f"  {gpt35_answer}")
        print(f"  (Tokens: {response.usage.total_tokens})\n")
    except openai.OpenAIError as e:
        print(f"  Error: {e}\n")


def main():
    """Run multi-provider example."""
    print("=== AmberTrace Multi-Provider Usage Example ===\n")

    # Step 1: Initialize AmberTrace once
    ambertrace_key = os.getenv("AMBERTRACE_API_KEY")
    if not ambertrace_key:
        print("ERROR: Please set AMBERTRACE_API_KEY environment variable")
        return

    print("1. Initializing AmberTrace (will trace all detected providers)...")
    ambertrace.init(
        api_key=ambertrace_key,
        environment="multi-provider-example",
        debug=False,  # Set to True to see trace collection logs
    )
    print(f"   ✓ AmberTrace initialized (tracing enabled: {ambertrace.is_enabled()})\n")

    # Step 2: Verify API keys
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if not openai_key:
        print("WARNING: OPENAI_API_KEY not set, OpenAI examples will be skipped")
    if not anthropic_key:
        print("WARNING: ANTHROPIC_API_KEY not set, Anthropic examples will be skipped")

    if not (openai_key or anthropic_key):
        print("ERROR: At least one provider API key must be set")
        return

    print("2. API keys configured\n")

    # Step 3: Compare models on various questions
    print("3. Comparing different LLM providers...")

    compare_models("What is the capital of France? Answer in one sentence.")

    compare_models("Explain quantum computing in simple terms (2 sentences max).")

    compare_models("What is 15 * 23? Show your work.")

    # Step 4: Show that both providers are traced
    print(f"\n{'='*70}")
    print("All API calls from both OpenAI and Anthropic have been traced!")
    print(f"{'='*70}\n")

    # Step 5: Flush all traces
    print("4. Flushing all pending traces...")
    ambertrace.flush(timeout=10.0)
    print("   ✓ All traces sent to backend\n")

    print("=== Example Complete ===\n")
    print("Check your AmberTrace dashboard to see:")
    print("  - Traces from both OpenAI and Anthropic")
    print("  - Unified format (same structure despite different providers)")
    print("  - Provider field distinguishes the source ('openai' vs 'anthropic')")
    print("  - Token usage normalized to common format")
    print("\nBoth providers were traced with a single ambertrace.init() call!")


if __name__ == "__main__":
    main()

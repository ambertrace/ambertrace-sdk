#!/usr/bin/env python3
"""Async usage example for AmberTrace SDK.

This example demonstrates:
- Initializing AmberTrace in async context
- Making asynchronous OpenAI API calls
- Automatic trace collection for async calls
- Async flushing of traces

Prerequisites:
    pip install ambertrace openai

Environment variables:
    AMBERTRACE_API_KEY - Your AmberTrace API key
    OPENAI_API_KEY - Your OpenAI API key
"""

import asyncio
import os

import openai

import ambertrace


async def make_single_call(client: openai.AsyncOpenAI, prompt: str, call_num: int) -> None:
    """Make a single async OpenAI API call.

    Args:
        client: AsyncOpenAI client instance
        prompt: User prompt to send
        call_num: Call number for logging
    """
    print(f"   Call {call_num}: Sending prompt: '{prompt}'")

    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=50,
        )

        assistant_message = response.choices[0].message.content
        print(f"   Call {call_num}: Response: {assistant_message}")
        print(f"   Call {call_num}: ✓ Success (tokens: {response.usage.total_tokens})\n")

    except openai.OpenAIError as e:
        print(f"   Call {call_num}: ✗ Error: {e}\n")


async def make_concurrent_calls(client: openai.AsyncOpenAI) -> None:
    """Make multiple concurrent async API calls.

    Args:
        client: AsyncOpenAI client instance
    """
    print("3. Making concurrent async API calls...")

    # Create multiple tasks
    tasks = [
        make_single_call(client, "What is Python?", 1),
        make_single_call(client, "What is JavaScript?", 2),
        make_single_call(client, "What is Rust?", 3),
    ]

    # Run concurrently
    await asyncio.gather(*tasks)

    print("   ✓ All concurrent calls completed\n")


async def demonstrate_error_tracing(client: openai.AsyncOpenAI) -> None:
    """Demonstrate error tracing with invalid parameters.

    Args:
        client: AsyncOpenAI client instance
    """
    print("4. Demonstrating error tracing...")

    try:
        # This will fail due to invalid model name
        response = await client.chat.completions.create(
            model="invalid-model-name",
            messages=[{"role": "user", "content": "Hello"}],
        )
    except openai.OpenAIError as e:
        print(f"   Expected error occurred: {type(e).__name__}")
        print(f"   ✓ Error was traced and will be sent to backend\n")


async def main() -> None:
    """Run async usage example."""
    print("=== AmberTrace Async Usage Example ===\n")

    # Step 1: Initialize AmberTrace
    ambertrace_key = os.getenv("AMBERTRACE_API_KEY")
    if not ambertrace_key:
        print("ERROR: Please set AMBERTRACE_API_KEY environment variable")
        return

    print("1. Initializing AmberTrace...")
    ambertrace.init(
        api_key=ambertrace_key,
        environment="async-example",
        debug=True,  # Enable debug logging
    )
    print(f"   ✓ AmberTrace initialized (enabled: {ambertrace.is_enabled()})\n")

    # Step 2: Create AsyncOpenAI client
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("ERROR: Please set OPENAI_API_KEY environment variable")
        return

    print("2. Creating AsyncOpenAI client...")
    client = openai.AsyncOpenAI(api_key=openai_key)
    print("   ✓ Async client created\n")

    # Step 3: Make concurrent calls
    await make_concurrent_calls(client)

    # Step 4: Demonstrate error tracing
    await demonstrate_error_tracing(client)

    # Step 5: Sequential calls
    print("5. Making sequential async calls...")
    await make_single_call(client, "Count to 3", 1)
    await make_single_call(client, "Name 3 colors", 2)
    print("   ✓ Sequential calls completed\n")

    # Step 6: Demonstrate async context awareness
    print("6. Testing disable/enable in async context...")
    ambertrace.disable()
    print(f"   ✓ Tracing disabled (enabled: {ambertrace.is_enabled()})")

    # This won't be traced
    await make_single_call(client, "This is not traced", 1)

    ambertrace.enable()
    print(f"   ✓ Tracing re-enabled (enabled: {ambertrace.is_enabled()})\n")

    # Step 7: Async flush
    print("7. Flushing pending traces (async)...")
    await ambertrace.flush_async(timeout=10.0)
    print("   ✓ All async traces sent to backend\n")

    print("=== Async Example Complete ===")
    print("\nCheck your AmberTrace dashboard to see the collected traces!")
    print("Note: Async traces are sent via asyncio tasks, not blocking threads.")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())

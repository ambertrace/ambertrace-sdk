#!/usr/bin/env python3
"""Anthropic Claude usage example for AmberTrace SDK.

This example demonstrates:
- Initializing AmberTrace
- Making synchronous Anthropic API calls
- Automatic trace collection for Claude models
- Flushing traces before exit

Prerequisites:
    pip install ambertrace anthropic

Environment variables:
    AMBERTRACE_API_KEY - Your AmberTrace API key
    ANTHROPIC_API_KEY - Your Anthropic API key
"""

import os

import anthropic

import ambertrace


def main():
    """Run Anthropic synchronous example."""
    print("=== AmberTrace Anthropic Usage Example ===\n")

    # Step 1: Initialize AmberTrace
    ambertrace_key = os.getenv("AMBERTRACE_API_KEY")
    if not ambertrace_key:
        print("ERROR: Please set AMBERTRACE_API_KEY environment variable")
        return

    print(f"1. Initializing AmberTrace...")
    ambertrace.init(
        api_key=ambertrace_key,
        environment="anthropic-example",
        debug=True,  # Enable debug logging to see trace collection
    )
    print(f"   ✓ AmberTrace initialized (tracing enabled: {ambertrace.is_enabled()})\n")

    # Step 2: Create Anthropic client
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("ERROR: Please set ANTHROPIC_API_KEY environment variable")
        return

    print("2. Creating Anthropic client...")
    client = anthropic.Anthropic(api_key=anthropic_key)
    print("   ✓ Anthropic client created\n")

    # Step 3: Make Anthropic API call (automatically traced!)
    print("3. Making Anthropic API call with Claude Opus (this will be traced automatically)...")
    try:
        response = client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Say hello in one short sentence."}
            ],
            temperature=0.7,
        )

        # Display response
        assistant_message = response.content[0].text
        print(f"   Response: {assistant_message}")
        print(f"   ✓ API call successful\n")

        # Show usage stats
        usage = response.usage
        print(f"   Token usage:")
        print(f"   - Input tokens: {usage.input_tokens}")
        print(f"   - Output tokens: {usage.output_tokens}")
        print(f"   - Total tokens: {usage.input_tokens + usage.output_tokens}\n")

    except anthropic.AnthropicError as e:
        print(f"   ✗ Anthropic API error: {e}\n")
        # Note: Even errors are traced!

    # Step 4: Make another call with system message
    print("4. Making call with system message...")
    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250514",
            max_tokens=50,
            system="You are a helpful math tutor.",  # System message (separate param in Anthropic)
            messages=[
                {"role": "user", "content": "What is 7 * 8?"}
            ],
        )

        assistant_message = response.content[0].text
        print(f"   Response: {assistant_message}")
        print(f"   ✓ Second call successful\n")

    except anthropic.AnthropicError as e:
        print(f"   ✗ Anthropic API error: {e}\n")

    # Step 5: Test disable/enable
    print("5. Testing disable/enable functionality...")
    ambertrace.disable()
    print(f"   ✓ Tracing disabled (enabled: {ambertrace.is_enabled()})")

    # This call won't be traced
    print("   Making API call (NOT traced)...")
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20250110",
            max_tokens=20,
            messages=[{"role": "user", "content": "Hi"}],
        )
        print(f"   ✓ Call completed (not traced)\n")
    except anthropic.AnthropicError as e:
        print(f"   ✗ Error: {e}\n")

    # Re-enable tracing
    ambertrace.enable()
    print(f"   ✓ Tracing re-enabled (enabled: {ambertrace.is_enabled()})\n")

    # Step 6: Flush traces before exit
    print("6. Flushing pending traces...")
    ambertrace.flush(timeout=10.0)
    print("   ✓ All traces sent to backend\n")

    print("=== Example Complete ===")
    print("\nCheck your AmberTrace dashboard to see the collected Anthropic traces!")
    print("Note: System messages are normalized and prepended to the messages array.")


if __name__ == "__main__":
    main()

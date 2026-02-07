#!/usr/bin/env python3
"""Basic usage example for AmberTrace SDK.

This example demonstrates:
- Initializing AmberTrace
- Making synchronous OpenAI API calls
- Automatic trace collection
- Flushing traces before exit

Prerequisites:
    pip install ambertrace openai

Environment variables:
    AMBERTRACE_API_KEY - Your AmberTrace API key
    OPENAI_API_KEY - Your OpenAI API key
"""

import os

import openai

import ambertrace


def main():
    """Run basic synchronous example."""
    print("=== AmberTrace Basic Usage Example ===\n")

    # Step 1: Initialize AmberTrace
    # API key can be passed as parameter or via AMBERTRACE_API_KEY env var
    ambertrace_key = os.getenv("AMBERTRACE_API_KEY")
    if not ambertrace_key:
        print("ERROR: Please set AMBERTRACE_API_KEY environment variable")
        return

    print(f"1. Initializing AmberTrace...")
    ambertrace.init(
        api_key=ambertrace_key,
        environment="example",  # Tag traces by environment
        debug=True,  # Enable debug logging to see trace collection
    )
    print(f"   ✓ AmberTrace initialized (tracing enabled: {ambertrace.is_enabled()})\n")

    # Step 2: Create OpenAI client
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("ERROR: Please set OPENAI_API_KEY environment variable")
        return

    print("2. Creating OpenAI client...")
    client = openai.OpenAI(api_key=openai_key)
    print("   ✓ OpenAI client created\n")

    # Step 3: Make OpenAI API call (automatically traced!)
    print("3. Making OpenAI API call (this will be traced automatically)...")
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello in one short sentence."},
            ],
            temperature=0.7,
            max_tokens=50,
        )

        # Display response
        assistant_message = response.choices[0].message.content
        print(f"   Response: {assistant_message}")
        print(f"   ✓ API call successful\n")

        # Show usage stats
        usage = response.usage
        print(f"   Token usage:")
        print(f"   - Prompt tokens: {usage.prompt_tokens}")
        print(f"   - Completion tokens: {usage.completion_tokens}")
        print(f"   - Total tokens: {usage.total_tokens}\n")

    except openai.OpenAIError as e:
        print(f"   ✗ OpenAI API error: {e}\n")
        # Note: Even errors are traced!

    # Step 4: Make another call to demonstrate multiple traces
    print("4. Making second API call...")
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "What is 2+2? Answer in one word."},
            ],
            temperature=0,
        )

        assistant_message = response.choices[0].message.content
        print(f"   Response: {assistant_message}")
        print(f"   ✓ Second call successful\n")

    except openai.OpenAIError as e:
        print(f"   ✗ OpenAI API error: {e}\n")

    # Step 5: Demonstrate disable/enable
    print("5. Testing disable/enable functionality...")
    ambertrace.disable()
    print(f"   ✓ Tracing disabled (enabled: {ambertrace.is_enabled()})")

    # This call won't be traced
    print("   Making API call (NOT traced)...")
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
        )
        print(f"   ✓ Call completed (not traced)\n")
    except openai.OpenAIError as e:
        print(f"   ✗ Error: {e}\n")

    # Re-enable tracing
    ambertrace.enable()
    print(f"   ✓ Tracing re-enabled (enabled: {ambertrace.is_enabled()})\n")

    # Step 6: Flush traces before exit
    print("6. Flushing pending traces...")
    ambertrace.flush(timeout=10.0)
    print("   ✓ All traces sent to backend\n")

    print("=== Example Complete ===")
    print("\nCheck your AmberTrace dashboard to see the collected traces!")


if __name__ == "__main__":
    main()

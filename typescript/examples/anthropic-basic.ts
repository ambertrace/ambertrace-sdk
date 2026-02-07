#!/usr/bin/env node
/**
 * Basic Anthropic usage example for AmberTrace TypeScript SDK.
 *
 * This example demonstrates:
 * - Initializing AmberTrace
 * - Making Anthropic API calls
 * - Automatic trace collection
 * - Flushing traces before exit
 *
 * Prerequisites:
 *     npm install @ambertrace/node @anthropic-ai/sdk
 *
 * Environment variables:
 *     AMBERTRACE_API_KEY - Your AmberTrace API key
 *     ANTHROPIC_API_KEY - Your Anthropic API key
 */

import ambertrace from '../src/index';
import Anthropic from '@anthropic-ai/sdk';

async function main() {
  console.log('=== AmberTrace Anthropic Basic Usage Example ===\n');

  // Step 1: Initialize AmberTrace
  const ambertraceApiKey = process.env.AMBERTRACE_API_KEY;
  if (!ambertraceApiKey) {
    console.error('ERROR: Please set AMBERTRACE_API_KEY environment variable');
    process.exit(1);
  }

  console.log('1. Initializing AmberTrace...');
  ambertrace.init({
    apiKey: ambertraceApiKey,
    environment: 'anthropic-example',
    debug: true, // Enable debug logging to see trace collection
  });
  console.log(`   ✓ AmberTrace initialized (tracing enabled: ${ambertrace.isEnabled()})\n`);

  // Step 2: Create Anthropic client
  const anthropicApiKey = process.env.ANTHROPIC_API_KEY;
  if (!anthropicApiKey) {
    console.error('ERROR: Please set ANTHROPIC_API_KEY environment variable');
    process.exit(1);
  }

  console.log('2. Creating Anthropic client...');
  const anthropic = new Anthropic({ apiKey: anthropicApiKey });
  console.log('   ✓ Anthropic client created\n');

  // Step 3: Make Anthropic API call (automatically traced!)
  console.log('3. Making Anthropic API call with Claude Opus (this will be traced automatically)...');
  try {
    const response = await anthropic.messages.create({
      model: 'claude-opus-4-5-20251101',
      max_tokens: 100,
      messages: [{ role: 'user', content: 'Say hello in one short sentence.' }],
      temperature: 0.7,
    });

    // Display response
    const message = response.content[0];
    if (message.type === 'text') {
      console.log(`   Response: ${message.text}`);
    }
    console.log('   ✓ API call successful\n');

    // Show usage stats
    const usage = response.usage;
    console.log('   Token usage:');
    console.log(`   - Input tokens: ${usage.input_tokens}`);
    console.log(`   - Output tokens: ${usage.output_tokens}`);
    console.log(`   - Total tokens: ${usage.input_tokens + usage.output_tokens}\n`);
  } catch (error) {
    console.error('   ✗ Anthropic API error:', error);
    // Note: Even errors are traced!
  }

  // Step 4: Make call with system message
  console.log('4. Making call with system message...');
  try {
    const response = await anthropic.messages.create({
      model: 'claude-sonnet-4-5-20250514',
      max_tokens: 50,
      system: 'You are a helpful math tutor.', // System message (separate param in Anthropic)
      messages: [{ role: 'user', content: 'What is 7 * 8?' }],
    });

    const message = response.content[0];
    if (message.type === 'text') {
      console.log(`   Response: ${message.text}`);
    }
    console.log('   ✓ Second call successful\n');
  } catch (error) {
    console.error('   ✗ Anthropic API error:', error);
  }

  // Step 5: Test disable/enable
  console.log('5. Testing disable/enable functionality...');
  ambertrace.disable();
  console.log(`   ✓ Tracing disabled (enabled: ${ambertrace.isEnabled()})`);

  // This call won't be traced
  console.log('   Making API call (NOT traced)...');
  try {
    await anthropic.messages.create({
      model: 'claude-haiku-4-5-20250110',
      max_tokens: 20,
      messages: [{ role: 'user', content: 'Hi' }],
    });
    console.log('   ✓ Call completed (not traced)\n');
  } catch (error) {
    console.error('   ✗ Error:', error, '\n');
  }

  // Re-enable tracing
  ambertrace.enable();
  console.log(`   ✓ Tracing re-enabled (enabled: ${ambertrace.isEnabled()})\n`);

  // Step 6: Flush traces before exit
  console.log('6. Flushing pending traces...');
  await ambertrace.flush(10000);
  console.log('   ✓ All traces sent to backend\n');

  console.log('=== Example Complete ===');
  console.log('\nCheck your AmberTrace dashboard to see the collected Anthropic traces!');
  console.log('Note: System messages are normalized and prepended to the messages array.');
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});

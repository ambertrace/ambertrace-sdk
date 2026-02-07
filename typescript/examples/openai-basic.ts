#!/usr/bin/env node
/**
 * Basic OpenAI usage example for AmberTrace TypeScript SDK.
 *
 * This example demonstrates:
 * - Initializing AmberTrace
 * - Making OpenAI API calls
 * - Automatic trace collection
 * - Flushing traces before exit
 *
 * Prerequisites:
 *     npm install @ambertrace/node openai
 *
 * Environment variables:
 *     AMBERTRACE_API_KEY - Your AmberTrace API key
 *     OPENAI_API_KEY - Your OpenAI API key
 */

import ambertrace from '../src/index';
import OpenAI from 'openai';

async function main() {
  console.log('=== AmberTrace OpenAI Basic Usage Example ===\n');

  // Step 1: Initialize AmberTrace
  const ambertraceApiKey = process.env.AMBERTRACE_API_KEY;
  if (!ambertraceApiKey) {
    console.error('ERROR: Please set AMBERTRACE_API_KEY environment variable');
    process.exit(1);
  }

  console.log('1. Initializing AmberTrace...');
  ambertrace.init({
    apiKey: ambertraceApiKey,
    environment: 'openai-example',
    debug: true, // Enable debug logging to see trace collection
  });
  console.log(`   ✓ AmberTrace initialized (tracing enabled: ${ambertrace.isEnabled()})\n`);

  // Step 2: Create OpenAI client
  const openaiApiKey = process.env.OPENAI_API_KEY;
  if (!openaiApiKey) {
    console.error('ERROR: Please set OPENAI_API_KEY environment variable');
    process.exit(1);
  }

  console.log('2. Creating OpenAI client...');
  const openai = new OpenAI({ apiKey: openaiApiKey });
  console.log('   ✓ OpenAI client created\n');

  // Step 3: Make OpenAI API call (automatically traced!)
  console.log('3. Making OpenAI API call (this will be traced automatically)...');
  try {
    const response = await openai.chat.completions.create({
      model: 'gpt-4',
      messages: [{ role: 'user', content: 'Say hello in one short sentence.' }],
      max_tokens: 50,
      temperature: 0.7,
    });

    // Display response
    const message = response.choices[0]?.message?.content;
    console.log(`   Response: ${message}`);
    console.log('   ✓ API call successful\n');

    // Show usage stats
    const usage = response.usage;
    if (usage) {
      console.log('   Token usage:');
      console.log(`   - Prompt tokens: ${usage.prompt_tokens}`);
      console.log(`   - Completion tokens: ${usage.completion_tokens}`);
      console.log(`   - Total tokens: ${usage.total_tokens}\n`);
    }
  } catch (error) {
    console.error('   ✗ OpenAI API error:', error);
    // Note: Even errors are traced!
  }

  // Step 4: Test disable/enable
  console.log('4. Testing disable/enable functionality...');
  ambertrace.disable();
  console.log(`   ✓ Tracing disabled (enabled: ${ambertrace.isEnabled()})`);

  // This call won't be traced
  console.log('   Making API call (NOT traced)...');
  try {
    await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [{ role: 'user', content: 'Hi' }],
      max_tokens: 10,
    });
    console.log('   ✓ Call completed (not traced)\n');
  } catch (error) {
    console.error('   ✗ Error:', error, '\n');
  }

  // Re-enable tracing
  ambertrace.enable();
  console.log(`   ✓ Tracing re-enabled (enabled: ${ambertrace.isEnabled()})\n`);

  // Step 5: Flush traces before exit
  console.log('5. Flushing pending traces...');
  await ambertrace.flush(10000);
  console.log('   ✓ All traces sent to backend\n');

  console.log('=== Example Complete ===');
  console.log('\nCheck your AmberTrace dashboard to see the collected OpenAI traces!');
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});

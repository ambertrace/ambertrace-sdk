#!/usr/bin/env node
/**
 * Multi-provider usage example for AmberTrace TypeScript SDK.
 *
 * This example demonstrates:
 * - Using multiple LLM providers simultaneously
 * - Single AmberTrace initialization traces all providers
 * - Comparing responses from different models
 * - Unified trace format for all providers
 *
 * Prerequisites:
 *     npm install @ambertrace/node openai @anthropic-ai/sdk
 *
 * Environment variables:
 *     AMBERTRACE_API_KEY - Your AmberTrace API key
 *     OPENAI_API_KEY - Your OpenAI API key
 *     ANTHROPIC_API_KEY - Your Anthropic API key
 */

import ambertrace from '../src/index';
import OpenAI from 'openai';
import Anthropic from '@anthropic-ai/sdk';

async function compareModels(question: string, openai: OpenAI, anthropic: Anthropic) {
  console.log(`\n${'='.repeat(70)}`);
  console.log(`Question: ${question}`);
  console.log(`${'='.repeat(70)}\n`);

  // Ask GPT-4
  console.log('GPT-4 (OpenAI):');
  try {
    const response = await openai.chat.completions.create({
      model: 'gpt-4',
      messages: [{ role: 'user', content: question }],
      max_tokens: 150,
    });
    const answer = response.choices[0]?.message?.content;
    console.log(`  ${answer}`);
    console.log(`  (Tokens: ${response.usage?.total_tokens})\n`);
  } catch (error) {
    console.error(`  Error: ${error}\n`);
  }

  // Ask Claude Opus
  console.log('Claude Opus (Anthropic):');
  try {
    const response = await anthropic.messages.create({
      model: 'claude-opus-4-5-20251101',
      max_tokens: 150,
      messages: [{ role: 'user', content: question }],
    });
    const message = response.content[0];
    const answer = message.type === 'text' ? message.text : '';
    const totalTokens = response.usage.input_tokens + response.usage.output_tokens;
    console.log(`  ${answer}`);
    console.log(`  (Tokens: ${totalTokens})\n`);
  } catch (error) {
    console.error(`  Error: ${error}\n`);
  }

  // Ask GPT-3.5-turbo (faster/cheaper)
  console.log('GPT-3.5-Turbo (OpenAI):');
  try {
    const response = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [{ role: 'user', content: question }],
      max_tokens: 150,
    });
    const answer = response.choices[0]?.message?.content;
    console.log(`  ${answer}`);
    console.log(`  (Tokens: ${response.usage?.total_tokens})\n`);
  } catch (error) {
    console.error(`  Error: ${error}\n`);
  }
}

async function main() {
  console.log('=== AmberTrace Multi-Provider Usage Example ===\n');

  // Step 1: Initialize AmberTrace once
  const ambertraceApiKey = process.env.AMBERTRACE_API_KEY;
  if (!ambertraceApiKey) {
    console.error('ERROR: Please set AMBERTRACE_API_KEY environment variable');
    process.exit(1);
  }

  console.log('1. Initializing AmberTrace (will trace all detected providers)...');
  ambertrace.init({
    apiKey: ambertraceApiKey,
    environment: 'multi-provider-example',
    debug: false, // Set to true to see trace collection logs
  });
  console.log(`   ✓ AmberTrace initialized (tracing enabled: ${ambertrace.isEnabled()})\n`);

  // Step 2: Verify API keys
  const openaiApiKey = process.env.OPENAI_API_KEY;
  const anthropicApiKey = process.env.ANTHROPIC_API_KEY;

  if (!openaiApiKey) {
    console.log('WARNING: OPENAI_API_KEY not set, OpenAI examples will be skipped');
  }
  if (!anthropicApiKey) {
    console.log('WARNING: ANTHROPIC_API_KEY not set, Anthropic examples will be skipped');
  }

  if (!openaiApiKey && !anthropicApiKey) {
    console.error('ERROR: At least one provider API key must be set');
    process.exit(1);
  }

  console.log('2. API keys configured\n');

  // Step 3: Create clients
  const openai = new OpenAI({ apiKey: openaiApiKey });
  const anthropic = new Anthropic({ apiKey: anthropicApiKey });

  // Step 4: Compare models on various questions
  console.log('3. Comparing different LLM providers...');

  await compareModels('What is the capital of France? Answer in one sentence.', openai, anthropic);

  await compareModels(
    'Explain quantum computing in simple terms (2 sentences max).',
    openai,
    anthropic
  );

  await compareModels('What is 15 * 23? Show your work.', openai, anthropic);

  // Step 5: Show that both providers are traced
  console.log(`\n${'='.repeat(70)}`);
  console.log('All API calls from both OpenAI and Anthropic have been traced!');
  console.log(`${'='.repeat(70)}\n`);

  // Step 6: Flush all traces
  console.log('4. Flushing all pending traces...');
  await ambertrace.flush(10000);
  console.log('   ✓ All traces sent to backend\n');

  console.log('=== Example Complete ===\n');
  console.log('Check your AmberTrace dashboard to see:');
  console.log('  - Traces from both OpenAI and Anthropic');
  console.log('  - Unified format (same structure despite different providers)');
  console.log("  - Provider field distinguishes the source ('openai' vs 'anthropic')");
  console.log('  - Token usage normalized to common format');
  console.log('\nBoth providers were traced with a single ambertrace.init() call!');
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});

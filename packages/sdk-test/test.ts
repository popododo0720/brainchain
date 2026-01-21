import { query, Options } from '@anthropic-ai/claude-agent-sdk';

async function main() {
  const options: Options = {
    maxThinkingTokens: 10000,
    includePartialMessages: true,
    allowedTools: [],
    cwd: '/tmp',
  };

  console.log('Starting query with thinking enabled...\n');

  for await (const message of query({
    prompt: 'What is 15 * 17? Think through this step by step.',
    options,
  })) {
    const msgType = (message as any).type;
    
    if (msgType === 'stream_event') {
      const event = (message as any).event;
      if (event?.type === 'content_block_start') {
        const blockType = event.content_block?.type;
        console.log(`\n--- Block Start: ${blockType} ---`);
      } else if (event?.type === 'content_block_delta') {
        const delta = event.delta;
        if (delta?.type === 'thinking_delta') {
          process.stdout.write(delta.thinking);
        } else if (delta?.type === 'text_delta') {
          process.stdout.write(delta.text);
        }
      }
    } else if (msgType === 'assistant') {
      const content = (message as any).message?.content || [];
      for (const block of content) {
        if (block.type === 'thinking') {
          console.log('\n\n=== THINKING BLOCK ===');
          console.log(block.thinking);
          console.log('=== END THINKING ===\n');
        } else if (block.type === 'text') {
          console.log('\n=== TEXT BLOCK ===');
          console.log(block.text);
          console.log('=== END TEXT ===\n');
        }
      }
    } else if (msgType === 'result') {
      console.log('\n\n--- Result ---');
      console.log('Status:', (message as any).subtype);
      console.log('Cost:', (message as any).total_cost_usd, 'USD');
    }
  }
}

main().catch(console.error);

import { Codex } from '@openai/codex-sdk';

async function main() {
  console.log('Starting Codex SDK test...\n');

  const codex = new Codex();
  const thread = codex.startThread({ skipGitRepoCheck: true });
  
  const { events } = await thread.runStreamed('What is 15 * 17? Think through this step by step.');

  for await (const event of events) {
    if (event.type === 'item.started' || event.type === 'item.updated' || event.type === 'item.completed') {
      const item = event.item;
      
      if (item.type === 'reasoning') {
        console.log('\n=== REASONING ===');
        console.log(item.text);
        console.log('=== END REASONING ===\n');
      } else if (item.type === 'agent_message') {
        console.log('\n=== AGENT MESSAGE ===');
        console.log(item.text);
        console.log('=== END MESSAGE ===\n');
      } else {
        console.log(`[${event.type}] ${item.type}:`, item.id);
      }
    } else if (event.type === 'turn.completed') {
      console.log('\n--- Turn Completed ---');
      console.log('Usage:', event.usage);
    } else if (event.type === 'error' || event.type === 'turn.failed') {
      console.error('Error:', event.message || event.error?.message);
    } else {
      console.log(`[${event.type}]`);
    }
  }
}

main().catch(console.error);

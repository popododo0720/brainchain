import { query } from '@anthropic-ai/claude-agent-sdk';
import { SDKConfig, emit } from './protocol.js';

export async function runClaude(
  prompt: string,
  config: SDKConfig,
  sessionId?: string
): Promise<string> {
  const agents: Record<string, { description: string; prompt: string; model?: 'sonnet' | 'opus' | 'haiku' | 'inherit' }> = {};
  
  for (const [name, def] of Object.entries(config.claudeAgents)) {
    let model: 'sonnet' | 'opus' | 'haiku' | 'inherit' | undefined;
    if (def.model) {
      if (def.model.includes('opus')) model = 'opus';
      else if (def.model.includes('haiku')) model = 'haiku';
      else if (def.model.includes('sonnet')) model = 'sonnet';
    }
    
    agents[name] = {
      description: def.description || `Execute ${name} tasks`,
      prompt: def.prompt,
      model,
    };
  }

  const allowedTools = config.allowedTools || [
    'Bash', 'Read', 'Write', 'Edit', 'MultiEdit',
    'Glob', 'Grep', 'LS',
    'WebFetch', 'WebSearch',
    'TodoRead', 'TodoWrite',
    'NotebookRead', 'NotebookEdit',
    'Task', 'Agent',
    'mcp__*'
  ];

  const options: Record<string, unknown> = {
    maxThinkingTokens: config.maxThinkingTokens || 32000,
    includePartialMessages: true,
    agents,
    allowedTools,
    cwd: process.cwd(),
    ...(sessionId ? { resume: sessionId } : {}),
  };

  if (config.mainAgent && agents[config.mainAgent]) {
    options.agent = config.mainAgent;
  }

  let thinkingBuffer = '';
  let textBuffer = '';
  let resultSessionId = sessionId || '';
  let totalCost = 0;
  let inputTokens = 0;
  let outputTokens = 0;

  try {
    for await (const message of query({ prompt, options })) {
      const msgType = (message as Record<string, unknown>).type as string;

      if (msgType === 'system') {
        const sys = message as Record<string, unknown>;
        resultSessionId = (sys.session_id as string) || resultSessionId;
        emit({
          type: 'system',
          sessionId: resultSessionId,
          model: (sys.model as string) || 'unknown',
        });
      }

      if (msgType === 'stream_event') {
        const event = (message as Record<string, unknown>).event as Record<string, unknown>;
        if (!event) continue;

        const eventType = event.type as string;

        if (eventType === 'content_block_start') {
          const block = event.content_block as Record<string, unknown>;
          if (block?.type === 'thinking') {
            thinkingBuffer = '';
          }
        }

        if (eventType === 'content_block_delta') {
          const delta = event.delta as Record<string, unknown>;
          if (!delta) continue;

          if (delta.type === 'thinking_delta') {
            const thinking = delta.thinking as string;
            thinkingBuffer += thinking;
            emit({ type: 'thinking', content: thinkingBuffer, delta: thinking });
          }

          if (delta.type === 'text_delta') {
            const text = delta.text as string;
            textBuffer += text;
            emit({ type: 'text', content: textBuffer, delta: text });
          }
        }
      }

      if (msgType === 'assistant') {
        const msg = (message as Record<string, unknown>).message as Record<string, unknown>;
        if (!msg) continue;

        const content = msg.content as Array<Record<string, unknown>>;
        if (!content) continue;

        for (const block of content) {
          if (block.type === 'thinking' && !thinkingBuffer) {
            thinkingBuffer = block.thinking as string;
            emit({ type: 'thinking', content: thinkingBuffer });
          }
          if (block.type === 'text' && !textBuffer) {
            textBuffer = block.text as string;
            emit({ type: 'text', content: textBuffer });
          }
          if (block.type === 'tool_use') {
            emit({
              type: 'tool_start',
              name: block.name as string,
              input: block.input,
            });
          }
        }
      }

      if (msgType === 'result') {
        const result = message as Record<string, unknown>;
        resultSessionId = (result.session_id as string) || resultSessionId;
        totalCost = (result.total_cost_usd as number) || 0;
        
        const usage = result.usage as Record<string, number> | undefined;
        if (usage) {
          inputTokens = usage.input_tokens || 0;
          outputTokens = usage.output_tokens || 0;
        }
      }
    }

    emit({
      type: 'result',
      status: 'success',
      sessionId: resultSessionId,
      output: textBuffer,
      usage: {
        inputTokens,
        outputTokens,
        totalCostUsd: totalCost,
      },
    });

    return textBuffer;
  } catch (error) {
    const errMsg = error instanceof Error ? error.message : String(error);
    emit({ type: 'error', message: errMsg });
    emit({ type: 'result', status: 'error', output: errMsg });
    return '';
  }
}

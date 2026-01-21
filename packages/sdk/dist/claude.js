import { query } from '@anthropic-ai/claude-agent-sdk';
import { emit } from './protocol.js';
export async function runClaude(prompt, config, sessionId) {
    const agents = {};
    for (const [name, def] of Object.entries(config.claudeAgents)) {
        let model;
        if (def.model) {
            if (def.model.includes('opus'))
                model = 'opus';
            else if (def.model.includes('haiku'))
                model = 'haiku';
            else if (def.model.includes('sonnet'))
                model = 'sonnet';
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
    const options = {
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
            const msgType = message.type;
            if (msgType === 'system') {
                const sys = message;
                resultSessionId = sys.session_id || resultSessionId;
                emit({
                    type: 'system',
                    sessionId: resultSessionId,
                    model: sys.model || 'unknown',
                });
            }
            if (msgType === 'stream_event') {
                const event = message.event;
                if (!event)
                    continue;
                const eventType = event.type;
                if (eventType === 'content_block_start') {
                    const block = event.content_block;
                    if (block?.type === 'thinking') {
                        thinkingBuffer = '';
                    }
                }
                if (eventType === 'content_block_delta') {
                    const delta = event.delta;
                    if (!delta)
                        continue;
                    if (delta.type === 'thinking_delta') {
                        const thinking = delta.thinking;
                        thinkingBuffer += thinking;
                        emit({ type: 'thinking', content: thinkingBuffer, delta: thinking });
                    }
                    if (delta.type === 'text_delta') {
                        const text = delta.text;
                        textBuffer += text;
                        emit({ type: 'text', content: textBuffer, delta: text });
                    }
                }
            }
            if (msgType === 'assistant') {
                const msg = message.message;
                if (!msg)
                    continue;
                const content = msg.content;
                if (!content)
                    continue;
                for (const block of content) {
                    if (block.type === 'thinking' && !thinkingBuffer) {
                        thinkingBuffer = block.thinking;
                        emit({ type: 'thinking', content: thinkingBuffer });
                    }
                    if (block.type === 'text' && !textBuffer) {
                        textBuffer = block.text;
                        emit({ type: 'text', content: textBuffer });
                    }
                    if (block.type === 'tool_use') {
                        emit({
                            type: 'tool_start',
                            name: block.name,
                            input: block.input,
                        });
                    }
                }
            }
            if (msgType === 'result') {
                const result = message;
                resultSessionId = result.session_id || resultSessionId;
                totalCost = result.total_cost_usd || 0;
                const usage = result.usage;
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
    }
    catch (error) {
        const errMsg = error instanceof Error ? error.message : String(error);
        emit({ type: 'error', message: errMsg });
        emit({ type: 'result', status: 'error', output: errMsg });
        return '';
    }
}
//# sourceMappingURL=claude.js.map
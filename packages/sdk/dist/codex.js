import { Codex } from '@openai/codex-sdk';
import { emit } from './protocol.js';
export async function runCodex(role, prompt, config) {
    const agentDef = config.codexAgents[role];
    if (!agentDef) {
        emit({ type: 'error', message: `Codex agent '${role}' not found in config` });
        emit({ type: 'result', status: 'error', output: `Agent '${role}' not found` });
        return '';
    }
    const fullPrompt = agentDef.prompt
        ? `${agentDef.prompt}\n\n---\n\nUser Request:\n${prompt}`
        : prompt;
    let reasoningBuffer = '';
    let textBuffer = '';
    let inputTokens = 0;
    let outputTokens = 0;
    try {
        const codex = new Codex();
        const thread = codex.startThread({ skipGitRepoCheck: true });
        emit({ type: 'system', sessionId: '', model: agentDef.model || 'codex' });
        const { events } = await thread.runStreamed(fullPrompt);
        for await (const event of events) {
            const eventType = event.type;
            if (eventType === 'item.started' || eventType === 'item.updated' || eventType === 'item.completed') {
                const item = event.item;
                if (item.type === 'reasoning') {
                    const newText = item.text || '';
                    const delta = newText.slice(reasoningBuffer.length);
                    reasoningBuffer = newText;
                    if (delta) {
                        emit({ type: 'reasoning', content: reasoningBuffer, delta });
                    }
                }
                else if (item.type === 'agent_message') {
                    const newText = item.text || '';
                    const delta = newText.slice(textBuffer.length);
                    textBuffer = newText;
                    if (delta) {
                        emit({ type: 'text', content: textBuffer, delta });
                    }
                }
                else if (item.type === 'command_execution') {
                    emit({
                        type: 'tool_start',
                        name: 'command_execution',
                        input: { command: item.command },
                    });
                    if (item.status === 'completed' || item.status === 'failed') {
                        emit({
                            type: 'tool_end',
                            name: 'command_execution',
                            output: item.aggregated_output,
                        });
                    }
                }
                else if (item.type === 'mcp_tool_call') {
                    emit({
                        type: 'tool_start',
                        name: `${item.server}:${item.tool}`,
                        input: item.arguments,
                    });
                    if (item.status === 'completed' || item.status === 'failed') {
                        emit({
                            type: 'tool_end',
                            name: `${item.server}:${item.tool}`,
                            output: item.result ? JSON.stringify(item.result) : item.error?.message,
                        });
                    }
                }
                else if (item.type === 'file_change') {
                    emit({
                        type: 'tool_start',
                        name: 'file_change',
                        input: { changes: item.changes },
                    });
                    if (item.status === 'completed' || item.status === 'failed') {
                        emit({
                            type: 'tool_end',
                            name: 'file_change',
                            output: `Status: ${item.status}`,
                        });
                    }
                }
            }
            else if (eventType === 'turn.completed') {
                const usage = event.usage;
                if (usage) {
                    inputTokens = usage.input_tokens || 0;
                    outputTokens = usage.output_tokens || 0;
                }
            }
            else if (eventType === 'error' || eventType === 'turn.failed') {
                const errEvent = event;
                const errMsg = errEvent.message ||
                    errEvent.error?.message ||
                    'Unknown error';
                emit({ type: 'error', message: errMsg });
            }
        }
        emit({
            type: 'result',
            status: 'success',
            output: textBuffer,
            usage: {
                inputTokens,
                outputTokens,
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
//# sourceMappingURL=codex.js.map
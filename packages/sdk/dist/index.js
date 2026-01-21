#!/usr/bin/env node
import * as readline from 'readline';
import { emit } from './protocol.js';
import { runClaude } from './claude.js';
import { runCodex } from './codex.js';
async function processRequest(req) {
    switch (req.action) {
        case 'chat':
            await runClaude(req.prompt, req.config, req.sessionId);
            break;
        case 'codex':
            await runCodex(req.role, req.prompt, req.config);
            break;
        default:
            emit({ type: 'error', message: `Unknown action: ${req.action}` });
            emit({ type: 'result', status: 'error', output: 'Unknown action' });
    }
}
async function main() {
    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout,
        terminal: false,
    });
    for await (const line of rl) {
        const trimmed = line.trim();
        if (!trimmed)
            continue;
        try {
            const req = JSON.parse(trimmed);
            await processRequest(req);
        }
        catch (error) {
            const errMsg = error instanceof Error ? error.message : String(error);
            emit({ type: 'error', message: `Failed to parse request: ${errMsg}` });
            emit({ type: 'result', status: 'error', output: errMsg });
        }
    }
}
main().catch((err) => {
    console.error('Fatal error:', err);
    process.exit(1);
});
//# sourceMappingURL=index.js.map
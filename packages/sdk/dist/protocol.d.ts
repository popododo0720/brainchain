export interface AgentDef {
    prompt: string;
    model?: string;
    description?: string;
}
export interface SDKConfig {
    claudeAgents: Record<string, AgentDef>;
    codexAgents: Record<string, AgentDef>;
    maxThinkingTokens?: number;
    allowedTools?: string[];
}
export interface ChatRequest {
    action: 'chat';
    prompt: string;
    config: SDKConfig;
    sessionId?: string;
}
export interface CallCodexRequest {
    action: 'codex';
    role: string;
    prompt: string;
    config: SDKConfig;
}
export type Request = ChatRequest | CallCodexRequest;
export type EventType = 'system' | 'thinking' | 'text' | 'reasoning' | 'tool_start' | 'tool_end' | 'error' | 'result';
export interface BaseEvent {
    type: EventType;
}
export interface SystemEvent extends BaseEvent {
    type: 'system';
    sessionId: string;
    model: string;
}
export interface ThinkingEvent extends BaseEvent {
    type: 'thinking';
    content: string;
    delta?: string;
}
export interface TextEvent extends BaseEvent {
    type: 'text';
    content: string;
    delta?: string;
}
export interface ReasoningEvent extends BaseEvent {
    type: 'reasoning';
    content: string;
    delta?: string;
}
export interface ToolStartEvent extends BaseEvent {
    type: 'tool_start';
    name: string;
    input?: unknown;
}
export interface ToolEndEvent extends BaseEvent {
    type: 'tool_end';
    name: string;
    output?: string;
}
export interface ErrorEvent extends BaseEvent {
    type: 'error';
    message: string;
}
export interface ResultEvent extends BaseEvent {
    type: 'result';
    status: 'success' | 'error';
    sessionId?: string;
    output?: string;
    usage?: {
        inputTokens: number;
        outputTokens: number;
        totalCostUsd?: number;
    };
}
export type Event = SystemEvent | ThinkingEvent | TextEvent | ReasoningEvent | ToolStartEvent | ToolEndEvent | ErrorEvent | ResultEvent;
export declare function emit(event: Event): void;
//# sourceMappingURL=protocol.d.ts.map
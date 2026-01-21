package sdk

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"

	"brainchain/cmd/chat/internal/config"
)

// Event types from SDK
type EventType string

const (
	EventSystem    EventType = "system"
	EventThinking  EventType = "thinking"
	EventText      EventType = "text"
	EventReasoning EventType = "reasoning"
	EventToolStart EventType = "tool_start"
	EventToolEnd   EventType = "tool_end"
	EventError     EventType = "error"
	EventResult    EventType = "result"
)

// Event is the JSON event from SDK subprocess
type Event struct {
	Type      EventType `json:"type"`
	Content   string    `json:"content,omitempty"`
	Delta     string    `json:"delta,omitempty"`
	SessionID string    `json:"sessionId,omitempty"`
	Model     string    `json:"model,omitempty"`
	Name      string    `json:"name,omitempty"`
	Input     any       `json:"input,omitempty"`
	Output    string    `json:"output,omitempty"`
	Message   string    `json:"message,omitempty"`
	Status    string    `json:"status,omitempty"`
	Usage     *Usage    `json:"usage,omitempty"`
}

type Usage struct {
	InputTokens  int     `json:"inputTokens"`
	OutputTokens int     `json:"outputTokens"`
	TotalCostUSD float64 `json:"totalCostUsd,omitempty"`
}

// AgentDef for SDK config
type AgentDef struct {
	Prompt      string `json:"prompt"`
	Model       string `json:"model,omitempty"`
	Description string `json:"description,omitempty"`
}

// SDKConfig for SDK subprocess
type SDKConfig struct {
	ClaudeAgents     map[string]AgentDef `json:"claudeAgents"`
	CodexAgents      map[string]AgentDef `json:"codexAgents"`
	MainAgent        string              `json:"mainAgent,omitempty"`
	MaxThinkingToken int                 `json:"maxThinkingTokens,omitempty"`
}

// ChatRequest for SDK subprocess
type ChatRequest struct {
	Action    string    `json:"action"`
	Prompt    string    `json:"prompt"`
	Config    SDKConfig `json:"config"`
	SessionID string    `json:"sessionId,omitempty"`
}

// CodexRequest for SDK subprocess
type CodexRequest struct {
	Action string    `json:"action"`
	Role   string    `json:"role"`
	Prompt string    `json:"prompt"`
	Config SDKConfig `json:"config"`
}

// Bridge manages SDK subprocess communication
type Bridge struct {
	sdkPath    string
	sdkConfig  SDKConfig
	mu         sync.Mutex
	currentCmd *exec.Cmd
}

// NewBridge creates a new SDK bridge from config
func NewBridge(cfg *config.Config, prompts map[string]string) (*Bridge, error) {
	// Find SDK path
	sdkPath, err := findSDKPath()
	if err != nil {
		return nil, fmt.Errorf("SDK not found: %w", err)
	}

	sdkConfig := SDKConfig{
		ClaudeAgents:     make(map[string]AgentDef),
		CodexAgents:      make(map[string]AgentDef),
		MaxThinkingToken: 32000,
	}

	if orchestratorPrompt, ok := prompts["orchestrator"]; ok {
		orchestratorAgent, ok := cfg.Agents[cfg.Orchestrator.Agent]
		model := ""
		if ok {
			model = orchestratorAgent.Model
		}
		sdkConfig.ClaudeAgents["orchestrator"] = AgentDef{
			Prompt:      orchestratorPrompt,
			Model:       model,
			Description: "Main orchestrator agent",
		}
		sdkConfig.MainAgent = "orchestrator"
	}

	for roleName, role := range cfg.Roles {
		agent, ok := cfg.Agents[role.Agent]
		if !ok {
			continue
		}

		prompt, ok := prompts[roleName]
		if !ok {
			prompt = fmt.Sprintf("You are %s.", roleName)
		}

		agentDef := AgentDef{
			Prompt:      prompt,
			Model:       agent.Model,
			Description: fmt.Sprintf("Execute %s tasks", roleName),
		}

		cmd := strings.ToLower(agent.Command)
		if cmd == "claude" {
			sdkConfig.ClaudeAgents[roleName] = agentDef
		} else if cmd == "codex" {
			sdkConfig.CodexAgents[roleName] = agentDef
		}
	}

	return &Bridge{
		sdkPath:   sdkPath,
		sdkConfig: sdkConfig,
	}, nil
}

// findSDKPath locates the SDK binary
func findSDKPath() (string, error) {
	candidates := []string{
		filepath.Join(os.Getenv("HOME"), ".config/brainchain/sdk/dist/index.js"),
		"./packages/sdk/dist/index.js",
		"../packages/sdk/dist/index.js",
	}

	if exePath, err := os.Executable(); err == nil {
		exeDir := filepath.Dir(exePath)
		candidates = append(candidates,
			filepath.Join(exeDir, "sdk/dist/index.js"),
			filepath.Join(exeDir, "../packages/sdk/dist/index.js"),
		)
	}

	for _, p := range candidates {
		if _, err := os.Stat(p); err == nil {
			abs, _ := filepath.Abs(p)
			return abs, nil
		}
	}

	return "", fmt.Errorf("SDK not found in any of: %v", candidates)
}

// StreamResult holds the final result of a stream
type StreamResult struct {
	Text      string
	Thinking  string
	Reasoning string
	Tools     []string
	SessionID string
	Usage     *Usage
	Error     string
}

// Chat streams a chat request through the SDK
func (b *Bridge) Chat(prompt, sessionID string, eventCh chan<- Event) (*StreamResult, error) {
	req := ChatRequest{
		Action:    "chat",
		Prompt:    prompt,
		Config:    b.sdkConfig,
		SessionID: sessionID,
	}

	return b.runSDK(req, eventCh)
}

// CallCodex calls a specific codex role
func (b *Bridge) CallCodex(role, prompt string, eventCh chan<- Event) (*StreamResult, error) {
	req := CodexRequest{
		Action: "codex",
		Role:   role,
		Prompt: prompt,
		Config: b.sdkConfig,
	}

	return b.runSDK(req, eventCh)
}

// Cancel kills the current SDK subprocess if running
func (b *Bridge) Cancel() {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.currentCmd != nil && b.currentCmd.Process != nil {
		b.currentCmd.Process.Kill()
		b.currentCmd = nil
	}
}

// runSDK executes the SDK subprocess
func (b *Bridge) runSDK(request any, eventCh chan<- Event) (*StreamResult, error) {
	cmd := exec.Command("node", b.sdkPath)
	cmd.Dir, _ = os.Getwd()

	b.mu.Lock()
	b.currentCmd = cmd
	b.mu.Unlock()

	defer func() {
		b.mu.Lock()
		b.currentCmd = nil
		b.mu.Unlock()
	}()

	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, fmt.Errorf("failed to get stdin: %w", err)
	}

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, fmt.Errorf("failed to get stdout: %w", err)
	}

	stderr, err := cmd.StderrPipe()
	if err != nil {
		return nil, fmt.Errorf("failed to get stderr: %w", err)
	}

	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("failed to start SDK: %w", err)
	}

	// Send request
	reqJSON, err := json.Marshal(request)
	if err != nil {
		cmd.Process.Kill()
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	if _, err := stdin.Write(append(reqJSON, '\n')); err != nil {
		cmd.Process.Kill()
		return nil, fmt.Errorf("failed to write request: %w", err)
	}
	stdin.Close()

	// Capture stderr in background
	var stderrBuf strings.Builder
	go func() {
		io.Copy(&stderrBuf, stderr)
	}()

	// Process events
	result := &StreamResult{}
	scanner := bufio.NewScanner(stdout)
	buf := make([]byte, 0, 1024*1024)
	scanner.Buffer(buf, 10*1024*1024)

	for scanner.Scan() {
		line := scanner.Text()
		if line == "" {
			continue
		}

		var event Event
		if err := json.Unmarshal([]byte(line), &event); err != nil {
			continue
		}

		if eventCh != nil {
			select {
			case eventCh <- event:
			default:
			}
		}

		// Accumulate result
		switch event.Type {
		case EventSystem:
			if event.SessionID != "" {
				result.SessionID = event.SessionID
			}
		case EventThinking:
			result.Thinking = event.Content
		case EventReasoning:
			result.Reasoning = event.Content
		case EventText:
			result.Text = event.Content
		case EventToolStart:
			result.Tools = append(result.Tools, event.Name)
		case EventError:
			result.Error = event.Message
		case EventResult:
			if event.SessionID != "" {
				result.SessionID = event.SessionID
			}
			if event.Usage != nil {
				result.Usage = event.Usage
			}
			if event.Status == "error" && result.Error == "" {
				result.Error = event.Output
			}
		}
	}

	if err := cmd.Wait(); err != nil {
		if result.Error == "" {
			result.Error = fmt.Sprintf("SDK process error: %v, stderr: %s", err, stderrBuf.String())
		}
	}

	return result, nil
}

// GetClaudeAgents returns agent names for Claude (for subagent registration)
func (b *Bridge) GetClaudeAgents() []string {
	names := make([]string, 0, len(b.sdkConfig.ClaudeAgents))
	for name := range b.sdkConfig.ClaudeAgents {
		names = append(names, name)
	}
	return names
}

// GetCodexAgents returns agent names for Codex
func (b *Bridge) GetCodexAgents() []string {
	names := make([]string, 0, len(b.sdkConfig.CodexAgents))
	for name := range b.sdkConfig.CodexAgents {
		names = append(names, name)
	}
	return names
}

// IsCodexRole checks if a role should be handled by Codex
func (b *Bridge) IsCodexRole(role string) bool {
	_, ok := b.sdkConfig.CodexAgents[role]
	return ok
}

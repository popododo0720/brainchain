package adapter

import (
	"context"
	"time"
)

type ClaudeAdapter struct {
	BaseAdapter
}

func NewClaudeAdapter(cfg *Config) *ClaudeAdapter {
	if cfg == nil {
		defaultCfg := Config{
			Command: "claude",
			Args:    []string{"-p", "{prompt}", "--print"},
			Timeout: 5 * time.Minute,
			Extra:   map[string]any{},
		}
		cfg = &defaultCfg
	}

	return &ClaudeAdapter{
		BaseAdapter: BaseAdapter{
			AdapterName:    "claude",
			AdapterDisplay: "Claude Code",
			Cfg:            *cfg,
		},
	}
}

func (a *ClaudeAdapter) BuildCommand(prompt string, opts map[string]any) []string {
	cmd := []string{a.Cfg.Command}

	for _, arg := range a.Cfg.Args {
		if arg == "{prompt}" {
			cmd = append(cmd, prompt)
		} else {
			cmd = append(cmd, arg)
		}
	}

	if model, ok := opts["model"].(string); ok && model != "" {
		cmd = append(cmd, "--model", model)
	} else if model, ok := a.Cfg.Extra["model"].(string); ok && model != "" {
		cmd = append(cmd, "--model", model)
	}

	if effort, ok := opts["effort"].(string); ok && effort != "" {
		cmd = append(cmd, "--effort", effort)
	} else if effort, ok := a.Cfg.Extra["effort"].(string); ok && effort != "" {
		cmd = append(cmd, "--effort", effort)
	}

	if tools, ok := opts["allowed_tools"].(string); ok && tools != "" {
		cmd = append(cmd, "--allowedTools", tools)
	} else if tools, ok := a.Cfg.Extra["allowed_tools"].(string); ok && tools != "" {
		cmd = append(cmd, "--allowedTools", tools)
	}

	return cmd
}

func (a *ClaudeAdapter) Run(ctx context.Context, prompt string, cwd string, opts map[string]any) (*Result, error) {
	return a.BaseAdapter.Run(ctx, prompt, cwd, opts, a.BuildCommand)
}

type ClaudeSonnetAdapter struct {
	ClaudeAdapter
}

func NewClaudeSonnetAdapter() *ClaudeSonnetAdapter {
	cfg := Config{
		Command: "claude",
		Args:    []string{"-p", "{prompt}", "--print"},
		Timeout: 5 * time.Minute,
		Extra:   map[string]any{"model": "sonnet"},
	}

	return &ClaudeSonnetAdapter{
		ClaudeAdapter: ClaudeAdapter{
			BaseAdapter: BaseAdapter{
				AdapterName:    "claude-sonnet",
				AdapterDisplay: "Claude Sonnet",
				Cfg:            cfg,
			},
		},
	}
}

type ClaudeOpusAdapter struct {
	ClaudeAdapter
}

func NewClaudeOpusAdapter() *ClaudeOpusAdapter {
	cfg := Config{
		Command: "claude",
		Args:    []string{"-p", "{prompt}", "--print"},
		Timeout: 5 * time.Minute,
		Extra:   map[string]any{"model": "opus"},
	}

	return &ClaudeOpusAdapter{
		ClaudeAdapter: ClaudeAdapter{
			BaseAdapter: BaseAdapter{
				AdapterName:    "claude-opus",
				AdapterDisplay: "Claude Opus",
				Cfg:            cfg,
			},
		},
	}
}

type ClaudeHaikuAdapter struct {
	ClaudeAdapter
}

func NewClaudeHaikuAdapter() *ClaudeHaikuAdapter {
	cfg := Config{
		Command: "claude",
		Args:    []string{"-p", "{prompt}", "--print"},
		Timeout: 5 * time.Minute,
		Extra:   map[string]any{"model": "haiku"},
	}

	return &ClaudeHaikuAdapter{
		ClaudeAdapter: ClaudeAdapter{
			BaseAdapter: BaseAdapter{
				AdapterName:    "claude-haiku",
				AdapterDisplay: "Claude Haiku",
				Cfg:            cfg,
			},
		},
	}
}

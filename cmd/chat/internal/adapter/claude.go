package adapter

import (
	"context"
	"time"
)

type ClaudeAdapter struct {
	BaseAdapter
}

// NewClaudeAdapter creates a Claude adapter with optional config
func NewClaudeAdapter(cfg *Config) *ClaudeAdapter {
	if cfg == nil {
		defaultCfg := Config{
			Command: "claude",
			Args:    []string{"-p", "{prompt}", "--print", "--permission-mode", "acceptEdits"},
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

// NewClaudeAdapterWithModel creates a Claude adapter for a specific model variant
func NewClaudeAdapterWithModel(model string) *ClaudeAdapter {
	displayNames := map[string]string{
		"":       "Claude Code",
		"sonnet": "Claude Sonnet",
		"opus":   "Claude Opus",
		"haiku":  "Claude Haiku",
	}

	adapterName := "claude"
	if model != "" {
		adapterName = "claude-" + model
	}

	display := displayNames[model]
	if display == "" {
		display = "Claude " + model
	}

	cfg := Config{
		Command: "claude",
		Args:    []string{"-p", "{prompt}", "--print", "--permission-mode", "acceptEdits"},
		Timeout: 5 * time.Minute,
		Extra:   map[string]any{},
	}

	if model != "" {
		cfg.Extra["model"] = model
	}

	return &ClaudeAdapter{
		BaseAdapter: BaseAdapter{
			AdapterName:    adapterName,
			AdapterDisplay: display,
			Cfg:            cfg,
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

	if model, ok := a.GetOption(opts, "model"); ok {
		cmd = append(cmd, "--model", model)
	}

	if tools, ok := a.GetOption(opts, "allowed_tools"); ok {
		cmd = append(cmd, "--allowedTools", tools)
	}

	return cmd
}

func (a *ClaudeAdapter) Run(ctx context.Context, prompt string, cwd string, opts map[string]any) (*Result, error) {
	return a.BaseAdapter.Run(ctx, prompt, cwd, opts, a.BuildCommand)
}

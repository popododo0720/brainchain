package adapter

import (
	"context"
	"time"
)

type CodexAdapter struct {
	BaseAdapter
}

func NewCodexAdapter(cfg *Config) *CodexAdapter {
	if cfg == nil {
		defaultCfg := Config{
			Command: "codex",
			Args:    []string{"exec", "{prompt}", "--full-auto", "--skip-git-repo-check"},
			Timeout: 5 * time.Minute,
			Extra:   map[string]any{},
		}
		cfg = &defaultCfg
	}

	return &CodexAdapter{
		BaseAdapter: BaseAdapter{
			AdapterName:    "codex",
			AdapterDisplay: "Codex CLI",
			Cfg:            *cfg,
		},
	}
}

func (a *CodexAdapter) BuildCommand(prompt string, opts map[string]any) []string {
	cmd := []string{a.Cfg.Command}

	if model, ok := a.GetOption(opts, "model"); ok {
		cmd = append(cmd, "-m", model)
	}

	for _, arg := range a.Cfg.Args {
		if arg == "{prompt}" {
			cmd = append(cmd, prompt)
		} else {
			cmd = append(cmd, arg)
		}
	}

	if effort, ok := a.GetOption(opts, "reasoning_effort"); ok {
		cmd = append(cmd, "--reasoning-effort", effort)
	}

	return cmd
}

func (a *CodexAdapter) Run(ctx context.Context, prompt string, cwd string, opts map[string]any) (*Result, error) {
	return a.BaseAdapter.Run(ctx, prompt, cwd, opts, a.BuildCommand)
}

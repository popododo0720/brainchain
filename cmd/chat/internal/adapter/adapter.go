package adapter

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"regexp"
	"strings"
	"time"
)

type Config struct {
	Command      string
	Args         []string
	Env          map[string]string
	Timeout      time.Duration
	Cwd          string
	StreamOutput bool
	Extra        map[string]any
}

func DefaultConfig(command string) Config {
	return Config{
		Command:      command,
		Args:         []string{},
		Env:          map[string]string{},
		Timeout:      5 * time.Minute,
		StreamOutput: true,
		Extra:        map[string]any{},
	}
}

type Result struct {
	Success    bool
	Output     string
	Error      string
	ExitCode   int
	DurationMs int64
	Adapter    string
	CommandRun string
}

type Adapter interface {
	Name() string
	DisplayName() string
	IsAvailable() bool
	BuildCommand(prompt string, opts map[string]any) []string
	ParseOutput(output string) string
	Run(ctx context.Context, prompt string, cwd string, opts map[string]any) (*Result, error)
	GetConfig() *Config
}

type BaseAdapter struct {
	AdapterName    string
	AdapterDisplay string
	Cfg            Config
}

func (a *BaseAdapter) Name() string {
	return a.AdapterName
}

func (a *BaseAdapter) DisplayName() string {
	return a.AdapterDisplay
}

func (a *BaseAdapter) IsAvailable() bool {
	_, err := exec.LookPath(a.AdapterName)
	return err == nil
}

func (a *BaseAdapter) GetConfig() *Config {
	return &a.Cfg
}

func (a *BaseAdapter) ParseOutput(output string) string {
	ansiRegex := regexp.MustCompile(`\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])`)
	output = ansiRegex.ReplaceAllString(output, "")

	spinnerRegex := regexp.MustCompile(`(?m)^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏].*$`)
	output = spinnerRegex.ReplaceAllString(output, "")

	return strings.TrimSpace(output)
}

func (a *BaseAdapter) Run(ctx context.Context, prompt string, cwd string, opts map[string]any, buildCmd func(string, map[string]any) []string) (*Result, error) {
	startTime := time.Now()

	cmd := buildCmd(prompt, opts)
	cmdStr := strings.Join(cmd, " ")

	workDir := cwd
	if workDir == "" {
		workDir = a.Cfg.Cwd
	}
	if workDir == "" {
		workDir, _ = os.Getwd()
	}

	timeout := a.Cfg.Timeout
	if timeout == 0 {
		timeout = 5 * time.Minute
	}

	execCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	execCmd := exec.CommandContext(execCtx, cmd[0], cmd[1:]...)
	execCmd.Dir = workDir

	if len(a.Cfg.Env) > 0 {
		execCmd.Env = os.Environ()
		for k, v := range a.Cfg.Env {
			execCmd.Env = append(execCmd.Env, fmt.Sprintf("%s=%s", k, v))
		}
	}

	var stdout, stderr bytes.Buffer
	execCmd.Stdout = &stdout
	execCmd.Stderr = &stderr

	err := execCmd.Run()
	durationMs := time.Since(startTime).Milliseconds()

	result := &Result{
		Adapter:    a.AdapterName,
		CommandRun: cmdStr,
		DurationMs: durationMs,
	}

	if execCtx.Err() == context.DeadlineExceeded {
		result.Success = false
		result.Error = fmt.Sprintf("Command timed out after %v", timeout)
		return result, nil
	}

	if err != nil {
		result.Success = false
		result.Error = stderr.String()
		if exitErr, ok := err.(*exec.ExitError); ok {
			result.ExitCode = exitErr.ExitCode()
		}
		return result, nil
	}

	result.Success = true
	result.Output = a.ParseOutput(stdout.String())
	result.ExitCode = 0

	return result, nil
}

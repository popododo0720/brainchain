package config

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/BurntSushi/toml"
)

type Config struct {
	Orchestrator OrchestratorConfig        `toml:"orchestrator"`
	Agents       map[string]AgentConfig    `toml:"agents"`
	Roles        map[string]RoleConfig     `toml:"roles"`
	Workflow     *WorkflowConfig           `toml:"workflow,omitempty"`
	RetryPolicy  RetryPolicyConfig         `toml:"retry_policy"`
	Parallel     ParallelConfig            `toml:"parallel"`
	Session      SessionConfig             `toml:"session"`
	MCP          MCPConfig                 `toml:"mcp"`
}

type OrchestratorConfig struct {
	Agent      string `toml:"agent"`
	PromptFile string `toml:"prompt_file"`
}

type AgentConfig struct {
	Command         string   `toml:"command"`
	Model           string   `toml:"model,omitempty"`
	Args            []string `toml:"args,omitempty"`
	Timeout         int      `toml:"timeout,omitempty"`
	ReasoningEffort string   `toml:"reasoning_effort,omitempty"`
}

type RoleConfig struct {
	Agent      string `toml:"agent"`
	PromptFile string `toml:"prompt_file"`
}

type WorkflowConfig struct {
	Steps []WorkflowStep `toml:"steps"`
}

type WorkflowStep struct {
	Role      string `toml:"role"`
	Output    string `toml:"output,omitempty"`
	Input     string `toml:"input,omitempty"`
	OnFail    string `toml:"on_fail,omitempty"`
	OnSuccess string `toml:"on_success,omitempty"`
	PerTask   bool   `toml:"per_task,omitempty"`
}

type RetryPolicyConfig struct {
	MaxRetries int `toml:"max_retries"`
	RetryDelay int `toml:"retry_delay"`
}

type ParallelConfig struct {
	MaxWorkers int `toml:"max_workers"`
}

type SessionConfig struct {
	Enabled       bool           `toml:"enabled"`
	AutoSave      bool           `toml:"auto_save"`
	RetentionDays int            `toml:"retention_days"`
	DBPath        string         `toml:"db_path,omitempty"`
	Recovery      RecoveryConfig `toml:"recovery"`
}

type RecoveryConfig struct {
	AutoDetect   bool `toml:"auto_detect"`
	PromptResume bool `toml:"prompt_resume"`
}

type MCPConfig struct {
	Enabled        bool                    `toml:"enabled"`
	ConnectTimeout int                     `toml:"connect_timeout"`
	Servers        map[string]ServerConfig `toml:"servers,omitempty"`
}

type ServerConfig struct {
	Enabled bool     `toml:"enabled"`
	Command []string `toml:"command"`
}

func GetConfigDir() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ".brainchain"
	}
	return filepath.Join(home, ".config", "brainchain")
}

func GetConfigPath() string {
	return filepath.Join(GetConfigDir(), "config.toml")
}

func Load(path string) (*Config, error) {
	if path == "" {
		path = GetConfigPath()
	}

	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("config not found: %s", path)
	}

	var config Config
	if err := toml.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("invalid config: %w", err)
	}

	if err := config.Validate(); err != nil {
		return nil, err
	}

	config.ApplyDefaults()

	return &config, nil
}

func (c *Config) Validate() error {
	if c.Orchestrator.Agent == "" {
		return fmt.Errorf("orchestrator.agent is required")
	}

	if _, ok := c.Agents[c.Orchestrator.Agent]; !ok {
		return fmt.Errorf("orchestrator agent '%s' not defined in agents", c.Orchestrator.Agent)
	}

	for name, agent := range c.Agents {
		if agent.Command == "" {
			return fmt.Errorf("agents.%s.command is required", name)
		}
	}

	for name, role := range c.Roles {
		if role.Agent == "" {
			return fmt.Errorf("roles.%s.agent is required", name)
		}
		if _, ok := c.Agents[role.Agent]; !ok {
			return fmt.Errorf("roles.%s uses undefined agent '%s'", name, role.Agent)
		}
	}

	return nil
}

func (c *Config) ApplyDefaults() {
	if c.RetryPolicy.MaxRetries == 0 {
		c.RetryPolicy.MaxRetries = 3
	}
	if c.RetryPolicy.RetryDelay == 0 {
		c.RetryPolicy.RetryDelay = 5
	}
	if c.Parallel.MaxWorkers == 0 {
		c.Parallel.MaxWorkers = 5
	}
	if c.Session.RetentionDays == 0 {
		c.Session.RetentionDays = 30
	}
	if c.MCP.ConnectTimeout == 0 {
		c.MCP.ConnectTimeout = 10
	}

	for name, agent := range c.Agents {
		if agent.Timeout == 0 {
			agent.Timeout = 300
			c.Agents[name] = agent
		}
	}
}

func LoadPrompts(config *Config, baseDir string) (map[string]string, error) {
	if baseDir == "" {
		baseDir = GetConfigDir()
	}

	prompts := make(map[string]string)

	if config.Orchestrator.PromptFile != "" {
		path := filepath.Join(baseDir, config.Orchestrator.PromptFile)
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("orchestrator prompt not found: %s", path)
		}
		prompts["orchestrator"] = string(data)
	}

	for name, role := range config.Roles {
		path := filepath.Join(baseDir, role.PromptFile)
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("prompt for role '%s' not found: %s", name, path)
		}
		prompts[name] = string(data)
	}

	return prompts, nil
}

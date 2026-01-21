package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"brainchain/cmd/chat/internal/config"
	"brainchain/cmd/chat/internal/executor"
	"brainchain/cmd/chat/internal/session"
	"brainchain/cmd/chat/internal/workflow"
)

func main() {
	var (
		initFlag     = flag.Bool("init", false, "Initialize configuration")
		listFlag     = flag.Bool("list", false, "List agents and roles")
		execRole     = flag.String("exec", "", "Execute role with prompt (use with -p)")
		prompt       = flag.String("p", "", "Prompt for -exec or -workflow")
		parallelFile = flag.String("parallel", "", "Run parallel tasks from JSON file")
		workflowFlag = flag.Bool("workflow", false, "Run complete workflow")
		sessionsFlag = flag.Bool("sessions", false, "List sessions")
		sessionInfo  = flag.String("session-info", "", "Show session details")

		cwdFlag      = flag.String("cwd", "", "Working directory")
		jsonFlag     = flag.Bool("json", false, "Output as JSON")
		configPath   = flag.String("config", "", "Config file path")
	)

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, `brainchain - Multi-CLI AI Orchestrator

Usage:
  brainchain [flags]

Flags:
`)
		flag.PrintDefaults()
		fmt.Fprintf(os.Stderr, `
Examples:
  brainchain                              # Launch TUI
  brainchain --list                       # List agents and roles
  brainchain --exec planner -p "Create auth system"
  brainchain --parallel tasks.json
  brainchain --workflow -p "Build a REST API"
  brainchain --sessions
`)
	}

	flag.Parse()

	if *initFlag {
		if err := cmdInit(); err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			os.Exit(1)
		}
		return
	}

	cwd := *cwdFlag
	if cwd == "" {
		cwd, _ = os.Getwd()
	}

	if !*listFlag && *execRole == "" && *parallelFile == "" && !*workflowFlag && !*sessionsFlag && *sessionInfo == "" {
		if err := runTUI(); err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			os.Exit(1)
		}
		return
	}

	cfg, err := config.Load(*configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading config: %v\n", err)
		os.Exit(1)
	}

	if *listFlag {
		cmdList(cfg, *jsonFlag)
		return
	}

	if *sessionsFlag {
		cmdSessions(cfg, *jsonFlag)
		return
	}

	if *sessionInfo != "" {
		cmdSessionInfo(cfg, *sessionInfo, *jsonFlag)
		return
	}

	prompts, err := config.LoadPrompts(cfg, "")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading prompts: %v\n", err)
		os.Exit(1)
	}

	exec := executor.New(cfg, prompts)

	if *execRole != "" {
		if *prompt == "" {
			fmt.Fprintf(os.Stderr, "Error: -p (prompt) required with -exec\n")
			os.Exit(1)
		}
		code := cmdExec(exec, *execRole, *prompt, cwd, *jsonFlag)
		os.Exit(code)
	}

	if *parallelFile != "" {
		code := cmdParallel(exec, *parallelFile, cwd, *jsonFlag)
		os.Exit(code)
	}

	if *workflowFlag {
		if *prompt == "" {
			fmt.Fprintf(os.Stderr, "Error: -p (prompt) required with -workflow\n")
			os.Exit(1)
		}
		code := cmdWorkflow(cfg, prompts, exec, *prompt, cwd, *jsonFlag)
		os.Exit(code)
	}
}



func cmdInit() error {
	home, err := os.UserHomeDir()
	if err != nil {
		return err
	}

	configDir := filepath.Join(home, ".config", "brainchain")
	if err := os.MkdirAll(configDir, 0755); err != nil {
		return err
	}

	configFile := filepath.Join(configDir, "config.toml")
	if _, err := os.Stat(configFile); os.IsNotExist(err) {
		srcConfig := filepath.Join(".", "config.toml")
		if data, err := os.ReadFile(srcConfig); err == nil {
			if err := os.WriteFile(configFile, data, 0644); err != nil {
				return err
			}
			fmt.Printf("Copied config.toml to %s\n", configFile)
		} else {
			fmt.Printf("Config directory created: %s\n", configDir)
			fmt.Println("Copy your config.toml to this directory")
		}
	} else {
		fmt.Printf("Config already exists: %s\n", configFile)
	}

	promptsDir := filepath.Join(configDir, "prompts")
	if err := os.MkdirAll(promptsDir, 0755); err != nil {
		return err
	}

	srcPrompts := filepath.Join(".", "prompts")
	if entries, err := os.ReadDir(srcPrompts); err == nil {
		for _, e := range entries {
			src := filepath.Join(srcPrompts, e.Name())
			dst := filepath.Join(promptsDir, e.Name())
			if data, err := os.ReadFile(src); err == nil {
				os.WriteFile(dst, data, 0644)
			}
		}
		fmt.Printf("Copied prompts to %s\n", promptsDir)
	}

	return nil
}

func cmdList(cfg *config.Config, asJSON bool) {
	if asJSON {
		data := map[string]any{
			"agents": cfg.Agents,
			"roles":  cfg.Roles,
		}
		if cfg.Workflow != nil {
			data["workflow"] = cfg.Workflow.Steps
		}
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		enc.Encode(data)
		return
	}

	fmt.Println("=== Agents ===")
	for name, agent := range cfg.Agents {
		model := agent.Model
		if model == "" {
			model = "default"
		}
		fmt.Printf("  %s: %s -m %s\n", name, agent.Command, model)
	}

	fmt.Println("\n=== Roles ===")
	for name, role := range cfg.Roles {
		fmt.Printf("  %s → %s\n", name, role.Agent)
	}

	if cfg.Workflow != nil && len(cfg.Workflow.Steps) > 0 {
		fmt.Println("\n=== Workflow Steps ===")
		for i, step := range cfg.Workflow.Steps {
			extra := ""
			if step.PerTask {
				extra += " (parallel)"
			}
			if step.OnFail != "" {
				extra += fmt.Sprintf(" [fail→%s]", step.OnFail)
			}
			if step.OnSuccess != "" {
				extra += fmt.Sprintf(" [success→%s]", step.OnSuccess)
			}
			fmt.Printf("  %d. %s%s\n", i+1, step.Role, extra)
		}
	}

	fmt.Printf("\nConfig: %s\n", config.GetConfigDir())
}

func cmdExec(exec *executor.Executor, role, prompt, cwd string, asJSON bool) int {
	ctx := context.Background()
	result, err := exec.RunSingleTask(ctx, role, prompt, "exec", cwd)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		return 1
	}

	if asJSON {
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		enc.Encode(result.ToMap())
	} else {
		if result.Success {
			fmt.Println(result.Output)
		} else {
			fmt.Fprintf(os.Stderr, "Task failed: %s\n", result.Error)
			return 1
		}
	}

	if result.Success {
		return 0
	}
	return 1
}

func cmdParallel(exec *executor.Executor, file, cwd string, asJSON bool) int {
	var data []byte
	var err error

	if file == "-" {
		data, err = io.ReadAll(os.Stdin)
	} else {
		data, err = os.ReadFile(file)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error reading file: %v\n", err)
		return 1
	}

	var tasks []struct {
		ID     string `json:"id"`
		Role   string `json:"role"`
		Prompt string `json:"prompt"`
	}
	if err := json.Unmarshal(data, &tasks); err != nil {
		fmt.Fprintf(os.Stderr, "Invalid JSON: %v\n", err)
		return 1
	}

	execTasks := make([]executor.Task, len(tasks))
	for i, t := range tasks {
		id := t.ID
		if id == "" {
			id = fmt.Sprintf("task%d", i+1)
		}
		execTasks[i] = executor.Task{ID: id, Role: t.Role, Prompt: t.Prompt}
	}

	ctx := context.Background()
	results := exec.RunParallelTasks(ctx, execTasks, cwd)

	resultMaps := make([]map[string]any, len(results))
	for i, r := range results {
		resultMaps[i] = r.ToMap()
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	enc.Encode(resultMaps)

	for _, r := range results {
		if !r.Success {
			return 1
		}
	}
	return 0
}

func cmdWorkflow(cfg *config.Config, prompts map[string]string, exec *executor.Executor, prompt, cwd string, asJSON bool) int {
	sess, _ := session.NewManager("", true)
	defer sess.Close()

	engine := workflow.New(cfg, prompts, exec, sess)

	if !asJSON {
		info := engine.GetInfo()
		fmt.Printf("Starting workflow with %d steps...\n\n", info["total_steps"])
	}

	ctx := context.Background()
	result := engine.Run(ctx, prompt, cwd, 10)

	if asJSON {
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		enc.Encode(result.ToMap())
	} else {
		if result.Success {
			fmt.Printf("\n✓ Workflow completed in %.2fs\n", result.TotalDuration.Seconds())
		} else {
			fmt.Fprintf(os.Stderr, "\n✗ Workflow failed: %s\n", result.Error)
		}
	}

	if result.Success {
		return 0
	}
	return 1
}

func cmdSessions(cfg *config.Config, asJSON bool) {
	mgr, err := session.NewManager("", true)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		return
	}
	defer mgr.Close()

	sessions, _ := mgr.ListSessions("", 20)

	if asJSON {
		var data []map[string]any
		for _, s := range sessions {
			data = append(data, s.ToMap())
		}
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		enc.Encode(data)
		return
	}

	if len(sessions) == 0 {
		fmt.Println("No sessions found.")
		return
	}

	fmt.Println("=== Sessions ===\n")
	for _, s := range sessions {
		icon := map[session.Status]string{
			session.StatusActive:      "⏳",
			session.StatusCompleted:   "✓",
			session.StatusFailed:      "✗",
			session.StatusInterrupted: "⚡",
		}[s.Status]

		preview := s.InitialPrompt
		if len(preview) > 50 {
			preview = preview[:50] + "..."
		}

		fmt.Printf("  %s [%s] %s\n", icon, s.ID[:8], s.Status)
		fmt.Printf("    Prompt: %s\n", preview)
		fmt.Printf("    Updated: %s\n\n", s.UpdatedAt.Format("2006-01-02 15:04"))
	}
}

func cmdSessionInfo(cfg *config.Config, sessionID string, asJSON bool) {
	mgr, err := session.NewManager("", true)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		return
	}
	defer mgr.Close()

	info, err := mgr.GetSessionInfo(sessionID)
	if err != nil || info == nil {
		fmt.Fprintf(os.Stderr, "Session not found: %s\n", sessionID)
		return
	}

	if asJSON {
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		enc.Encode(info)
		return
	}

	sess := info["session"].(map[string]any)
	fmt.Printf("=== Session %s ===\n\n", sessionID[:8])
	fmt.Printf("Status: %s\n", sess["status"])
	fmt.Printf("Created: %s\n", sess["created_at"])
	fmt.Printf("Updated: %s\n", sess["updated_at"])
	fmt.Printf("CWD: %s\n", sess["cwd"])
	fmt.Printf("\nInitial Prompt:\n%s\n", sess["initial_prompt"])

	if messages, ok := info["messages"].([]map[string]any); ok && len(messages) > 0 {
		fmt.Printf("\n=== Messages (%d) ===\n", len(messages))
		for _, m := range messages {
			content := m["content"].(string)
			if len(content) > 100 {
				content = content[:100] + "..."
			}
			fmt.Printf("  [%s] %s\n", m["role"], content)
		}
	}
}

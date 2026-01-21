package executor

import (
	"context"
	"fmt"
	"sync"
	"time"

	"brainchain/cmd/chat/internal/adapter"
	"brainchain/cmd/chat/internal/config"
)

type TaskResult struct {
	TaskID   string
	Role     string
	Agent    string
	Success  bool
	Output   string
	Error    string
	Duration time.Duration
	Retries  int
}

func (r *TaskResult) ToMap() map[string]any {
	return map[string]any{
		"id":       r.TaskID,
		"role":     r.Role,
		"agent":    r.Agent,
		"success":  r.Success,
		"output":   r.Output,
		"error":    r.Error,
		"duration": r.Duration.Seconds(),
		"retries":  r.Retries,
	}
}

type Task struct {
	ID     string
	Role   string
	Prompt string
}

type Executor struct {
	cfg        *config.Config
	prompts    map[string]string
	maxRetries int
	retryDelay time.Duration
	maxWorkers int
}

func NewExecutor(cfg *config.Config, prompts map[string]string) *Executor {
	return &Executor{
		cfg:        cfg,
		prompts:    prompts,
		maxRetries: cfg.RetryPolicy.MaxRetries,
		retryDelay: time.Duration(cfg.RetryPolicy.RetryDelay) * time.Second,
		maxWorkers: cfg.Parallel.MaxWorkers,
	}
}

func (e *Executor) RunSingleTask(ctx context.Context, role string, prompt string, taskID string, cwd string) (*TaskResult, error) {
	roleConfig, ok := e.cfg.Roles[role]
	if !ok {
		return nil, fmt.Errorf("unknown role: %s", role)
	}

	agentConfig, ok := e.cfg.Agents[roleConfig.Agent]
	if !ok {
		return nil, fmt.Errorf("unknown agent: %s", roleConfig.Agent)
	}

	adp := e.createAdapter(roleConfig.Agent, &agentConfig)
	if adp == nil {
		return nil, fmt.Errorf("failed to create adapter for agent: %s", roleConfig.Agent)
	}

	rolePrompt := e.prompts[role]
	fullPrompt := fmt.Sprintf("%s\n\n---\n\n%s", rolePrompt, prompt)

	var result *TaskResult
	var lastErr error

	for attempt := 0; attempt <= e.maxRetries; attempt++ {
		if attempt > 0 {
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(e.retryDelay):
			}
		}

		startTime := time.Now()
		adpResult, err := adp.Run(ctx, fullPrompt, cwd, nil)
		duration := time.Since(startTime)

		if err != nil {
			lastErr = err
			continue
		}

		result = &TaskResult{
			TaskID:   taskID,
			Role:     role,
			Agent:    roleConfig.Agent,
			Success:  adpResult.Success,
			Output:   adpResult.Output,
			Error:    adpResult.Error,
			Duration: duration,
			Retries:  attempt,
		}

		if adpResult.Success {
			return result, nil
		}

		lastErr = fmt.Errorf(adpResult.Error)
	}

	if result != nil {
		return result, nil
	}

	return &TaskResult{
		TaskID:  taskID,
		Role:    role,
		Agent:   roleConfig.Agent,
		Success: false,
		Error:   lastErr.Error(),
		Retries: e.maxRetries,
	}, nil
}

func (e *Executor) RunParallelTasks(ctx context.Context, tasks []Task, cwd string) []*TaskResult {
	if len(tasks) == 0 {
		return nil
	}

	workers := e.maxWorkers
	if len(tasks) < workers {
		workers = len(tasks)
	}

	taskChan := make(chan Task, len(tasks))
	resultChan := make(chan *TaskResult, len(tasks))

	var wg sync.WaitGroup
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for task := range taskChan {
				result, err := e.RunSingleTask(ctx, task.Role, task.Prompt, task.ID, cwd)
				if err != nil {
					result = &TaskResult{
						TaskID:  task.ID,
						Role:    task.Role,
						Success: false,
						Error:   err.Error(),
					}
				}
				resultChan <- result
			}
		}()
	}

	for _, task := range tasks {
		taskChan <- task
	}
	close(taskChan)

	go func() {
		wg.Wait()
		close(resultChan)
	}()

	resultMap := make(map[string]*TaskResult)
	for result := range resultChan {
		resultMap[result.TaskID] = result
	}

	results := make([]*TaskResult, len(tasks))
	for i, task := range tasks {
		if r, ok := resultMap[task.ID]; ok {
			results[i] = r
		} else {
			results[i] = &TaskResult{
				TaskID:  task.ID,
				Role:    task.Role,
				Success: false,
				Error:   "result not found",
			}
		}
	}

	return results
}

func (e *Executor) createAdapter(agentName string, agentConfig *config.AgentConfig) adapter.Adapter {
	cfg := adapter.Config{
		Command: agentConfig.Command,
		Args:    agentConfig.Args,
		Timeout: time.Duration(agentConfig.Timeout) * time.Second,
		Extra:   map[string]any{},
	}

	if agentConfig.Model != "" {
		cfg.Extra["model"] = agentConfig.Model
	}
	if agentConfig.ReasoningEffort != "" {
		cfg.Extra["reasoning_effort"] = agentConfig.ReasoningEffort
	}

	switch agentConfig.Command {
	case "claude":
		if len(cfg.Args) == 0 {
			cfg.Args = []string{"-p", "{prompt}", "--print"}
		}
		return adapter.NewClaudeAdapter(&cfg)
	case "codex":
		if len(cfg.Args) == 0 {
			cfg.Args = []string{"exec", "{prompt}", "--full-auto", "--skip-git-repo-check"}
		}
		return adapter.NewCodexAdapter(&cfg)
	default:
		return nil
	}
}

func (e *Executor) GetAdapter(name string) adapter.Adapter {
	if agentConfig, ok := e.cfg.Agents[name]; ok {
		return e.createAdapter(name, &agentConfig)
	}
	return adapter.Get(name)
}

package workflow

import (
	"context"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
	"time"

	"brainchain/cmd/chat/internal/config"
	"brainchain/cmd/chat/internal/executor"
	"brainchain/cmd/chat/internal/session"
)

type StepResult struct {
	StepIndex   int
	Role        string
	Success     bool
	Duration    time.Duration
	Output      string
	Error       string
	TaskResults []*executor.TaskResult
	JumpTarget  string
}

func (r *StepResult) ToMap() map[string]any {
	taskMaps := make([]map[string]any, len(r.TaskResults))
	for i, t := range r.TaskResults {
		taskMaps[i] = t.ToMap()
	}
	return map[string]any{
		"step_index":   r.StepIndex,
		"role":         r.Role,
		"success":      r.Success,
		"duration":     r.Duration.Seconds(),
		"output":       r.Output,
		"error":        r.Error,
		"task_results": taskMaps,
		"jump_target":  r.JumpTarget,
	}
}

type Result struct {
	Success        bool
	StepsCompleted int
	TotalSteps     int
	StepResults    []*StepResult
	TotalDuration  time.Duration
	FinalOutput    string
	Error          string
}

func (r *Result) ToMap() map[string]any {
	steps := make([]map[string]any, len(r.StepResults))
	for i, s := range r.StepResults {
		steps[i] = s.ToMap()
	}
	return map[string]any{
		"success":         r.Success,
		"steps_completed": r.StepsCompleted,
		"total_steps":     r.TotalSteps,
		"step_results":    steps,
		"total_duration":  r.TotalDuration.Seconds(),
		"final_output":    r.FinalOutput,
		"error":           r.Error,
	}
}

type Engine struct {
	cfg      *config.Config
	prompts  map[string]string
	exec     *executor.Executor
	session  *session.Manager
	steps    []config.WorkflowStep
	roleStep map[string]int
	outputs  map[string]string
	plan     map[string]any
	cwd      string
}

func New(cfg *config.Config, prompts map[string]string, exec *executor.Executor, sess *session.Manager) *Engine {
	roleStep := make(map[string]int)
	steps := []config.WorkflowStep{}
	if cfg.Workflow != nil {
		steps = cfg.Workflow.Steps
		for i, step := range steps {
			if _, exists := roleStep[step.Role]; !exists {
				roleStep[step.Role] = i
			}
		}
	}

	return &Engine{
		cfg:      cfg,
		prompts:  prompts,
		exec:     exec,
		session:  sess,
		steps:    steps,
		roleStep: roleStep,
		outputs:  make(map[string]string),
	}
}

func (e *Engine) Run(ctx context.Context, initialPrompt, cwd string, maxLoops int) *Result {
	if len(e.steps) == 0 {
		return &Result{Success: false, Error: "no workflow steps defined"}
	}

	e.cwd = cwd
	e.outputs["initial_prompt"] = initialPrompt
	start := time.Now()

	var results []*StepResult
	currentStep := 0
	visits := make(map[int]int)

	for currentStep < len(e.steps) {
		visits[currentStep]++
		if visits[currentStep] > maxLoops {
			return &Result{
				Success:        false,
				StepsCompleted: len(results),
				TotalSteps:     len(e.steps),
				StepResults:    results,
				TotalDuration:  time.Since(start),
				Error:          fmt.Sprintf("max loops (%d) exceeded at step %d", maxLoops, currentStep+1),
			}
		}

		step := e.steps[currentStep]
		result := e.executeStep(ctx, currentStep, step, initialPrompt)
		results = append(results, result)

		e.saveState(currentStep, results)

		if result.JumpTarget != "" {
			if target, ok := e.resolveJump(result.JumpTarget); ok {
				currentStep = target
				continue
			}
		}

		if !result.Success {
			return &Result{
				Success:        false,
				StepsCompleted: len(results),
				TotalSteps:     len(e.steps),
				StepResults:    results,
				TotalDuration:  time.Since(start),
				Error:          result.Error,
			}
		}

		currentStep++
	}

	return &Result{
		Success:        true,
		StepsCompleted: len(results),
		TotalSteps:     len(e.steps),
		StepResults:    results,
		TotalDuration:  time.Since(start),
		FinalOutput:    e.outputs["final"],
	}
}

func (e *Engine) executeStep(ctx context.Context, idx int, step config.WorkflowStep, initialPrompt string) *StepResult {
	start := time.Now()

	var result *StepResult
	if step.PerTask && e.plan != nil {
		result = e.executePerTask(ctx, idx, step)
	} else {
		result = e.executeSingle(ctx, idx, step, initialPrompt)
	}

	result.Duration = time.Since(start)

	if step.Output != "" && result.Success {
		e.outputs[step.Output] = result.Output
		if step.Output == "plan.json" {
			e.parsePlan(result.Output)
		}
	}

	if !result.Success && step.OnFail != "" {
		result.JumpTarget = step.OnFail
	} else if result.Success && step.OnSuccess != "" {
		result.JumpTarget = step.OnSuccess
	}

	return result
}

func (e *Engine) executeSingle(ctx context.Context, idx int, step config.WorkflowStep, initialPrompt string) *StepResult {
	prompt := e.buildPrompt(step, initialPrompt)

	taskResult, err := e.exec.RunSingleTask(ctx, step.Role, prompt, fmt.Sprintf("step%d", idx+1), e.cwd)
	if err != nil {
		return &StepResult{
			StepIndex: idx,
			Role:      step.Role,
			Success:   false,
			Error:     err.Error(),
		}
	}

	success := taskResult.Success
	if success && (step.Role == "plan_validator" || step.Role == "code_reviewer") {
		success = checkVerdict(taskResult.Output)
	}

	return &StepResult{
		StepIndex:   idx,
		Role:        step.Role,
		Success:     success,
		Output:      taskResult.Output,
		Error:       taskResult.Error,
		TaskResults: []*executor.TaskResult{taskResult},
	}
}

func (e *Engine) executePerTask(ctx context.Context, idx int, step config.WorkflowStep) *StepResult {
	tasks, ok := e.plan["tasks"].([]any)
	if !ok || len(tasks) == 0 {
		return &StepResult{
			StepIndex: idx,
			Role:      step.Role,
			Success:   false,
			Error:     "no tasks in plan",
		}
	}

	execTasks := make([]executor.Task, 0, len(tasks))
	for i, t := range tasks {
		task, ok := t.(map[string]any)
		if !ok {
			continue
		}
		taskID, _ := task["id"].(string)
		if taskID == "" {
			taskID = fmt.Sprintf("task%d", i+1)
		}
		prompt := e.buildTaskPrompt(task)
		execTasks = append(execTasks, executor.Task{
			ID:     taskID,
			Role:   step.Role,
			Prompt: prompt,
		})
	}

	results := e.exec.RunParallelTasks(ctx, execTasks, e.cwd)

	allSuccess := true
	var outputs []string
	var errors []string
	for _, r := range results {
		if !r.Success {
			allSuccess = false
			if r.Error != "" {
				errors = append(errors, r.Error)
			}
		}
		if r.Output != "" {
			outputs = append(outputs, r.Output)
		}
	}

	return &StepResult{
		StepIndex:   idx,
		Role:        step.Role,
		Success:     allSuccess,
		Output:      strings.Join(outputs, "\n---\n"),
		Error:       strings.Join(errors, "; "),
		TaskResults: results,
	}
}

func (e *Engine) buildPrompt(step config.WorkflowStep, initialPrompt string) string {
	var parts []string

	if step.Role == "planner" {
		parts = append(parts, fmt.Sprintf("User Request:\n%s", initialPrompt))
	}

	if step.Input != "" {
		if content, ok := e.outputs[step.Input]; ok {
			parts = append(parts, fmt.Sprintf("Input (%s):\n%s", step.Input, content))
		}
	}

	if e.plan != nil && step.Role != "planner" {
		planJSON, _ := json.MarshalIndent(e.plan, "", "  ")
		parts = append(parts, fmt.Sprintf("Current Plan:\n```json\n%s\n```", planJSON))
	}

	if len(parts) == 0 {
		return initialPrompt
	}
	return strings.Join(parts, "\n\n")
}

func (e *Engine) buildTaskPrompt(task map[string]any) string {
	var lines []string

	if id, ok := task["id"].(string); ok {
		lines = append(lines, fmt.Sprintf("Task ID: %s", id))
	}
	if desc, ok := task["description"].(string); ok {
		lines = append(lines, fmt.Sprintf("Description: %s", desc))
	}
	if files, ok := task["files"].([]any); ok {
		var fileStrs []string
		for _, f := range files {
			if s, ok := f.(string); ok {
				fileStrs = append(fileStrs, s)
			}
		}
		lines = append(lines, fmt.Sprintf("Files: %s", strings.Join(fileStrs, ", ")))
	}
	if criteria, ok := task["acceptance_criteria"].([]any); ok {
		lines = append(lines, "Acceptance Criteria:")
		for _, c := range criteria {
			if s, ok := c.(string); ok {
				lines = append(lines, fmt.Sprintf("  - %s", s))
			}
		}
	}

	if specs, ok := e.plan["specs"].([]any); ok {
		lines = append(lines, "\nRelevant Specs:")
		for _, s := range specs {
			spec, ok := s.(map[string]any)
			if !ok {
				continue
			}
			file, _ := spec["file"].(string)
			content, _ := spec["content"].(string)
			lines = append(lines, fmt.Sprintf("--- %s ---\n%s", file, content))
		}
	}

	return strings.Join(lines, "\n")
}

func (e *Engine) parsePlan(output string) {
	jsonRe := regexp.MustCompile("(?s)```(?:json)?\\s*\\n?([\\s\\S]*?)\\n?```")
	matches := jsonRe.FindStringSubmatch(output)

	var jsonStr string
	if len(matches) > 1 {
		jsonStr = matches[1]
	} else {
		jsonStr = output
	}

	var plan map[string]any
	if err := json.Unmarshal([]byte(jsonStr), &plan); err == nil {
		e.plan = plan
	}
}

func (e *Engine) resolveJump(target string) (int, bool) {
	if !strings.HasPrefix(target, "goto:") {
		return 0, false
	}
	role := strings.TrimPrefix(target, "goto:")
	if idx, ok := e.roleStep[role]; ok {
		return idx, true
	}
	return 0, false
}

func (e *Engine) saveState(currentStep int, results []*StepResult) {
	if e.session == nil {
		return
	}

	stepMaps := make([]map[string]any, len(results))
	for i, r := range results {
		stepMaps[i] = r.ToMap()
	}

	e.session.SaveWorkflowState("", currentStep, stepMaps, e.plan, e.outputs)
}

func (e *Engine) GetInfo() map[string]any {
	steps := make([]map[string]any, len(e.steps))
	for i, s := range e.steps {
		steps[i] = map[string]any{
			"index":      i + 1,
			"role":       s.Role,
			"input":      s.Input,
			"output":     s.Output,
			"per_task":   s.PerTask,
			"on_fail":    s.OnFail,
			"on_success": s.OnSuccess,
		}
	}

	roles := make([]string, 0, len(e.cfg.Roles))
	for r := range e.cfg.Roles {
		roles = append(roles, r)
	}

	return map[string]any{
		"total_steps":     len(e.steps),
		"steps":           steps,
		"available_roles": roles,
	}
}

func (e *Engine) RestoreState(plan map[string]any, outputs map[string]string) {
	if plan != nil {
		e.plan = plan
	}
	if outputs != nil {
		e.outputs = outputs
	}
}

func checkVerdict(output string) bool {
	lower := strings.ToLower(output)

	if strings.Contains(lower, `"verdict"`) {
		if strings.Contains(lower, `"approved"`) || strings.Contains(lower, `"passed"`) {
			return true
		}
		if strings.Contains(lower, `"needs_revision"`) || strings.Contains(lower, `"failed"`) {
			return false
		}
	}

	if strings.Contains(lower, "approved") || strings.Contains(lower, "passed") {
		return true
	}
	if strings.Contains(lower, "needs_revision") || strings.Contains(lower, "failed") {
		return false
	}

	return true
}

package workflow

import (
	"encoding/json"
	"fmt"
	"regexp"
)

// Plan represents a structured execution plan
type Plan struct {
	Tasks []Task `json:"tasks"`
	Specs []Spec `json:"specs,omitempty"`
}

// Task represents a single work item in the plan
type Task struct {
	ID                 string   `json:"id"`
	Description        string   `json:"description"`
	Files              []string `json:"files,omitempty"`
	AcceptanceCriteria []string `json:"acceptance_criteria,omitempty"`
}

// Spec represents a specification/documentation for implementation
type Spec struct {
	File    string `json:"file"`
	Content string `json:"content"`
}

// ParsePlan attempts to parse a plan from output text (with or without code blocks)
func ParsePlan(output string) (*Plan, error) {
	jsonRe := regexp.MustCompile("(?s)```(?:json)?\\s*\\n?([\\s\\S]*?)\\n?```")
	matches := jsonRe.FindStringSubmatch(output)

	var jsonStr string
	if len(matches) > 1 {
		jsonStr = matches[1]
	} else {
		jsonStr = output
	}

	var plan Plan
	if err := json.Unmarshal([]byte(jsonStr), &plan); err != nil {
		return nil, fmt.Errorf("invalid plan JSON: %w", err)
	}
	return &plan, nil
}

// ToMap converts Plan to map[string]any for backward compatibility (e.g., session storage)
func (p *Plan) ToMap() map[string]any {
	if p == nil {
		return nil
	}

	tasks := make([]map[string]any, len(p.Tasks))
	for i, t := range p.Tasks {
		task := map[string]any{
			"id":          t.ID,
			"description": t.Description,
		}
		if len(t.Files) > 0 {
			task["files"] = t.Files
		}
		if len(t.AcceptanceCriteria) > 0 {
			task["acceptance_criteria"] = t.AcceptanceCriteria
		}
		tasks[i] = task
	}

	specs := make([]map[string]any, len(p.Specs))
	for i, s := range p.Specs {
		specs[i] = map[string]any{
			"file":    s.File,
			"content": s.Content,
		}
	}

	result := map[string]any{
		"tasks": tasks,
	}
	if len(specs) > 0 {
		result["specs"] = specs
	}
	return result
}

// PlanFromMap creates a Plan from map[string]any (for restoring from session)
func PlanFromMap(m map[string]any) *Plan {
	if m == nil {
		return nil
	}

	plan := &Plan{}

	if tasks, ok := m["tasks"].([]any); ok {
		for _, t := range tasks {
			if taskMap, ok := t.(map[string]any); ok {
				task := Task{}
				if id, ok := taskMap["id"].(string); ok {
					task.ID = id
				}
				if desc, ok := taskMap["description"].(string); ok {
					task.Description = desc
				}
				if files, ok := taskMap["files"].([]any); ok {
					for _, f := range files {
						if s, ok := f.(string); ok {
							task.Files = append(task.Files, s)
						}
					}
				}
				if criteria, ok := taskMap["acceptance_criteria"].([]any); ok {
					for _, c := range criteria {
						if s, ok := c.(string); ok {
							task.AcceptanceCriteria = append(task.AcceptanceCriteria, s)
						}
					}
				}
				plan.Tasks = append(plan.Tasks, task)
			}
		}
	}

	if specs, ok := m["specs"].([]any); ok {
		for _, s := range specs {
			if specMap, ok := s.(map[string]any); ok {
				spec := Spec{}
				if file, ok := specMap["file"].(string); ok {
					spec.File = file
				}
				if content, ok := specMap["content"].(string); ok {
					spec.Content = content
				}
				plan.Specs = append(plan.Specs, spec)
			}
		}
	}

	return plan
}

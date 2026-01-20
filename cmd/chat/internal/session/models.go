package session

import (
	"encoding/json"
	"time"
)

type Status string

const (
	StatusActive      Status = "active"
	StatusCompleted   Status = "completed"
	StatusFailed      Status = "failed"
	StatusInterrupted Status = "interrupted"
)

type Session struct {
	ID             string
	CreatedAt      time.Time
	UpdatedAt      time.Time
	Status         Status
	WorkflowName   string
	InitialPrompt  string
	Cwd            string
	ConfigSnapshot map[string]any
	Name           string
	AutoName       string
}

func (s *Session) DisplayName() string {
	if s.Name != "" {
		return s.Name
	}
	if s.AutoName != "" {
		return s.AutoName
	}
	if len(s.ID) >= 8 {
		return s.ID[:8]
	}
	return s.ID
}

func (s *Session) ToMap() map[string]any {
	return map[string]any{
		"id":              s.ID,
		"created_at":      s.CreatedAt.Format(time.RFC3339),
		"updated_at":      s.UpdatedAt.Format(time.RFC3339),
		"status":          string(s.Status),
		"workflow_name":   s.WorkflowName,
		"initial_prompt":  s.InitialPrompt,
		"cwd":             s.Cwd,
		"config_snapshot": s.ConfigSnapshot,
		"name":            s.Name,
		"auto_name":       s.AutoName,
	}
}

type Message struct {
	ID        string
	SessionID string
	Timestamp time.Time
	Role      string
	Content   string
	StepIndex *int
	TaskID    string
}

func (m *Message) ToMap() map[string]any {
	result := map[string]any{
		"id":         m.ID,
		"session_id": m.SessionID,
		"timestamp":  m.Timestamp.Format(time.RFC3339),
		"role":       m.Role,
		"content":    m.Content,
		"task_id":    m.TaskID,
	}
	if m.StepIndex != nil {
		result["step_index"] = *m.StepIndex
	}
	return result
}

type ToolInvocation struct {
	ID         string
	SessionID  string
	Timestamp  time.Time
	ToolType   string
	ToolName   string
	Arguments  map[string]any
	Result     any
	Success    bool
	DurationMs int64
}

func (t *ToolInvocation) ToMap() map[string]any {
	return map[string]any{
		"id":          t.ID,
		"session_id":  t.SessionID,
		"timestamp":   t.Timestamp.Format(time.RFC3339),
		"tool_type":   t.ToolType,
		"tool_name":   t.ToolName,
		"arguments":   t.Arguments,
		"result":      t.Result,
		"success":     t.Success,
		"duration_ms": t.DurationMs,
	}
}

type WorkflowState struct {
	SessionID   string
	CurrentStep int
	StepResults []map[string]any
	Plan        map[string]any
	Outputs     map[string]string
}

func (w *WorkflowState) ToMap() map[string]any {
	return map[string]any{
		"session_id":   w.SessionID,
		"current_step": w.CurrentStep,
		"step_results": w.StepResults,
		"plan":         w.Plan,
		"outputs":      w.Outputs,
	}
}

func jsonMarshal(v any) string {
	if v == nil {
		return ""
	}
	b, err := json.Marshal(v)
	if err != nil {
		return ""
	}
	return string(b)
}

func jsonUnmarshalMap(s string) map[string]any {
	if s == "" {
		return nil
	}
	var m map[string]any
	if err := json.Unmarshal([]byte(s), &m); err != nil {
		return nil
	}
	return m
}

func jsonUnmarshalSlice(s string) []map[string]any {
	if s == "" {
		return nil
	}
	var m []map[string]any
	if err := json.Unmarshal([]byte(s), &m); err != nil {
		return nil
	}
	return m
}

func jsonUnmarshalMapString(s string) map[string]string {
	if s == "" {
		return nil
	}
	var m map[string]string
	if err := json.Unmarshal([]byte(s), &m); err != nil {
		return nil
	}
	return m
}

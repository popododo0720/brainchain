package session

import (
	"os"
	"path/filepath"
	"time"

	"github.com/google/uuid"
)

func GetDefaultDBPath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return filepath.Join(".brainchain", "sessions.db")
	}
	return filepath.Join(home, ".config", "brainchain", "sessions.db")
}

type Manager struct {
	db               *Database
	enabled          bool
	autoSave         bool
	currentSessionID string
}

func NewManager(dbPath string, enabled bool) (*Manager, error) {
	if !enabled {
		return &Manager{enabled: false}, nil
	}

	if dbPath == "" {
		dbPath = GetDefaultDBPath()
	}

	db, err := NewDatabase(dbPath)
	if err != nil {
		return nil, err
	}

	return &Manager{
		db:       db,
		enabled:  true,
		autoSave: true,
	}, nil
}

func (m *Manager) Close() error {
	if m.db != nil {
		return m.db.Close()
	}
	return nil
}

func (m *Manager) CreateSession(initialPrompt, cwd, workflowName string, configSnapshot map[string]any) (*Session, error) {
	if !m.enabled || m.db == nil {
		return nil, nil
	}

	now := time.Now()
	session := &Session{
		ID:             uuid.New().String(),
		CreatedAt:      now,
		UpdatedAt:      now,
		Status:         StatusActive,
		WorkflowName:   workflowName,
		InitialPrompt:  initialPrompt,
		Cwd:            cwd,
		ConfigSnapshot: configSnapshot,
	}

	if err := m.db.CreateSession(session); err != nil {
		return nil, err
	}

	m.currentSessionID = session.ID
	return session, nil
}

func (m *Manager) GetSession(sessionID string) (*Session, error) {
	if !m.enabled || m.db == nil {
		return nil, nil
	}
	return m.db.GetSession(sessionID)
}

func (m *Manager) CurrentSession() (*Session, error) {
	if m.currentSessionID == "" {
		return nil, nil
	}
	return m.GetSession(m.currentSessionID)
}

func (m *Manager) SetCurrentSession(sessionID string) bool {
	if !m.enabled || m.db == nil {
		return false
	}
	session, err := m.db.GetSession(sessionID)
	if err != nil || session == nil {
		return false
	}
	m.currentSessionID = sessionID
	return true
}

func (m *Manager) UpdateStatus(sessionID string, status Status) error {
	if !m.enabled || m.db == nil {
		return nil
	}
	return m.db.UpdateSessionStatus(sessionID, status)
}

func (m *Manager) CompleteSession(sessionID string) error {
	sid := sessionID
	if sid == "" {
		sid = m.currentSessionID
	}
	if sid == "" {
		return nil
	}

	if err := m.UpdateStatus(sid, StatusCompleted); err != nil {
		return err
	}

	if sid == m.currentSessionID {
		m.currentSessionID = ""
	}
	return nil
}

func (m *Manager) FailSession(sessionID string, errMsg string) error {
	sid := sessionID
	if sid == "" {
		sid = m.currentSessionID
	}
	if sid == "" {
		return nil
	}

	if errMsg != "" {
		m.AddMessage(sid, "system", "Session failed: "+errMsg, nil, "")
	}

	if err := m.UpdateStatus(sid, StatusFailed); err != nil {
		return err
	}

	if sid == m.currentSessionID {
		m.currentSessionID = ""
	}
	return nil
}

func (m *Manager) InterruptSession(sessionID string) error {
	sid := sessionID
	if sid == "" {
		sid = m.currentSessionID
	}
	if sid == "" {
		return nil
	}
	return m.UpdateStatus(sid, StatusInterrupted)
}

func (m *Manager) ListSessions(status Status, limit int) ([]*Session, error) {
	if !m.enabled || m.db == nil {
		return nil, nil
	}
	return m.db.ListSessions(status, limit)
}

func (m *Manager) GetSessionInfo(sessionID string) (map[string]any, error) {
	if !m.enabled || m.db == nil {
		return nil, nil
	}
	return m.db.GetSessionInfo(sessionID)
}

func (m *Manager) DeleteSession(sessionID string) error {
	if !m.enabled || m.db == nil {
		return nil
	}
	return m.db.DeleteSession(sessionID)
}

func (m *Manager) CleanupOldSessions(retentionDays int) (int64, error) {
	if !m.enabled || m.db == nil {
		return 0, nil
	}
	return m.db.CleanupOldSessions(retentionDays)
}

func (m *Manager) AddMessage(sessionID, role, content string, stepIndex *int, taskID string) (*Message, error) {
	if !m.enabled || m.db == nil {
		return nil, nil
	}

	sid := sessionID
	if sid == "" {
		sid = m.currentSessionID
	}
	if sid == "" {
		return nil, nil
	}

	msg := &Message{
		ID:        uuid.New().String(),
		SessionID: sid,
		Timestamp: time.Now(),
		Role:      role,
		Content:   content,
		StepIndex: stepIndex,
		TaskID:    taskID,
	}

	if err := m.db.AddMessage(msg); err != nil {
		return nil, err
	}
	return msg, nil
}

func (m *Manager) GetMessages(sessionID string) ([]*Message, error) {
	if !m.enabled || m.db == nil {
		return nil, nil
	}

	sid := sessionID
	if sid == "" {
		sid = m.currentSessionID
	}
	if sid == "" {
		return nil, nil
	}
	return m.db.GetMessages(sid)
}

func (m *Manager) RecordToolInvocation(sessionID, toolType, toolName string, args map[string]any, result any, success bool, durationMs int64) (*ToolInvocation, error) {
	if !m.enabled || m.db == nil {
		return nil, nil
	}

	sid := sessionID
	if sid == "" {
		sid = m.currentSessionID
	}
	if sid == "" {
		return nil, nil
	}

	inv := &ToolInvocation{
		ID:         uuid.New().String(),
		SessionID:  sid,
		Timestamp:  time.Now(),
		ToolType:   toolType,
		ToolName:   toolName,
		Arguments:  args,
		Result:     result,
		Success:    success,
		DurationMs: durationMs,
	}

	if err := m.db.AddToolInvocation(inv); err != nil {
		return nil, err
	}
	return inv, nil
}

func (m *Manager) GetToolInvocations(sessionID string) ([]*ToolInvocation, error) {
	if !m.enabled || m.db == nil {
		return nil, nil
	}

	sid := sessionID
	if sid == "" {
		sid = m.currentSessionID
	}
	if sid == "" {
		return nil, nil
	}
	return m.db.GetToolInvocations(sid)
}

func (m *Manager) SaveWorkflowState(sessionID string, currentStep int, stepResults []map[string]any, plan map[string]any, outputs map[string]string) (*WorkflowState, error) {
	if !m.enabled || m.db == nil {
		return nil, nil
	}

	sid := sessionID
	if sid == "" {
		sid = m.currentSessionID
	}
	if sid == "" {
		return nil, nil
	}

	state := &WorkflowState{
		SessionID:   sid,
		CurrentStep: currentStep,
		StepResults: stepResults,
		Plan:        plan,
		Outputs:     outputs,
	}

	if err := m.db.SaveWorkflowState(state); err != nil {
		return nil, err
	}
	return state, nil
}

func (m *Manager) GetWorkflowState(sessionID string) (*WorkflowState, error) {
	if !m.enabled || m.db == nil {
		return nil, nil
	}

	sid := sessionID
	if sid == "" {
		sid = m.currentSessionID
	}
	if sid == "" {
		return nil, nil
	}
	return m.db.GetWorkflowState(sid)
}

func (m *Manager) GetInterruptedSessions() ([]*Session, error) {
	if !m.enabled || m.db == nil {
		return nil, nil
	}
	return m.db.GetInterruptedSessions()
}

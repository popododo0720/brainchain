package session

import (
	"database/sql"
	"encoding/json"
	"os"
	"path/filepath"
	"time"

	_ "modernc.org/sqlite"
)

const schemaSQL = `
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    workflow_name TEXT,
    initial_prompt TEXT NOT NULL,
    cwd TEXT NOT NULL,
    config_snapshot TEXT NOT NULL,
    name TEXT,
    auto_name TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    step_index INTEGER,
    task_id TEXT
);

CREATE TABLE IF NOT EXISTS tool_invocations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    tool_type TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments TEXT NOT NULL,
    result TEXT,
    success INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_states (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    current_step INTEGER NOT NULL,
    step_results TEXT NOT NULL,
    plan TEXT,
    outputs TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_invocations_session ON tool_invocations(session_id);
`

type Database struct {
	db     *sql.DB
	dbPath string
}

func NewDatabase(dbPath string) (*Database, error) {
	dir := filepath.Dir(dbPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, err
	}

	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, err
	}

	db.SetMaxOpenConns(1)

	if _, err := db.Exec("PRAGMA foreign_keys = ON"); err != nil {
		db.Close()
		return nil, err
	}

	if _, err := db.Exec(schemaSQL); err != nil {
		db.Close()
		return nil, err
	}

	return &Database{db: db, dbPath: dbPath}, nil
}

func (d *Database) Close() error {
	return d.db.Close()
}

func (d *Database) CreateSession(s *Session) error {
	configJSON, _ := json.Marshal(s.ConfigSnapshot)
	_, err := d.db.Exec(`
		INSERT INTO sessions (id, created_at, updated_at, status, workflow_name, initial_prompt, cwd, config_snapshot, name, auto_name)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`, s.ID, s.CreatedAt.Format(time.RFC3339), s.UpdatedAt.Format(time.RFC3339),
		string(s.Status), s.WorkflowName, s.InitialPrompt, s.Cwd, string(configJSON), s.Name, s.AutoName)
	return err
}

func (d *Database) GetSession(id string) (*Session, error) {
	row := d.db.QueryRow(`SELECT * FROM sessions WHERE id = ?`, id)
	return d.scanSession(row)
}

func (d *Database) scanSession(row *sql.Row) (*Session, error) {
	var s Session
	var createdAt, updatedAt, status, configJSON string
	var workflowName, name, autoName sql.NullString

	err := row.Scan(&s.ID, &createdAt, &updatedAt, &status, &workflowName,
		&s.InitialPrompt, &s.Cwd, &configJSON, &name, &autoName)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}

	s.CreatedAt, _ = time.Parse(time.RFC3339, createdAt)
	s.UpdatedAt, _ = time.Parse(time.RFC3339, updatedAt)
	s.Status = Status(status)
	s.WorkflowName = workflowName.String
	s.Name = name.String
	s.AutoName = autoName.String
	json.Unmarshal([]byte(configJSON), &s.ConfigSnapshot)

	return &s, nil
}

func (d *Database) UpdateSessionStatus(id string, status Status) error {
	_, err := d.db.Exec(`UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?`,
		string(status), time.Now().Format(time.RFC3339), id)
	return err
}

func (d *Database) UpdateSessionName(id string, name, autoName string) error {
	_, err := d.db.Exec(`UPDATE sessions SET name = ?, auto_name = ?, updated_at = ? WHERE id = ?`,
		name, autoName, time.Now().Format(time.RFC3339), id)
	return err
}

func (d *Database) ListSessions(status Status, limit int) ([]*Session, error) {
	var rows *sql.Rows
	var err error

	if status != "" {
		rows, err = d.db.Query(`
			SELECT * FROM sessions WHERE status = ? ORDER BY updated_at DESC LIMIT ?
		`, string(status), limit)
	} else {
		rows, err = d.db.Query(`
			SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?
		`, limit)
	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var sessions []*Session
	for rows.Next() {
		var s Session
		var createdAt, updatedAt, statusStr, configJSON string
		var workflowName, name, autoName sql.NullString

		err := rows.Scan(&s.ID, &createdAt, &updatedAt, &statusStr, &workflowName,
			&s.InitialPrompt, &s.Cwd, &configJSON, &name, &autoName)
		if err != nil {
			continue
		}

		s.CreatedAt, _ = time.Parse(time.RFC3339, createdAt)
		s.UpdatedAt, _ = time.Parse(time.RFC3339, updatedAt)
		s.Status = Status(statusStr)
		s.WorkflowName = workflowName.String
		s.Name = name.String
		s.AutoName = autoName.String
		json.Unmarshal([]byte(configJSON), &s.ConfigSnapshot)

		sessions = append(sessions, &s)
	}

	return sessions, nil
}

func (d *Database) DeleteSession(id string) error {
	_, err := d.db.Exec(`DELETE FROM sessions WHERE id = ?`, id)
	return err
}

func (d *Database) CleanupOldSessions(retentionDays int) (int64, error) {
	cutoff := time.Now().AddDate(0, 0, -retentionDays)
	result, err := d.db.Exec(`
		DELETE FROM sessions WHERE updated_at < ? AND status IN (?, ?)
	`, cutoff.Format(time.RFC3339), string(StatusCompleted), string(StatusFailed))
	if err != nil {
		return 0, err
	}
	return result.RowsAffected()
}

func (d *Database) AddMessage(m *Message) error {
	var stepIndex sql.NullInt64
	if m.StepIndex != nil {
		stepIndex.Int64 = int64(*m.StepIndex)
		stepIndex.Valid = true
	}

	_, err := d.db.Exec(`
		INSERT INTO messages (id, session_id, timestamp, role, content, step_index, task_id)
		VALUES (?, ?, ?, ?, ?, ?, ?)
	`, m.ID, m.SessionID, m.Timestamp.Format(time.RFC3339), m.Role, m.Content, stepIndex, m.TaskID)
	return err
}

func (d *Database) GetMessages(sessionID string) ([]*Message, error) {
	rows, err := d.db.Query(`
		SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC
	`, sessionID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var messages []*Message
	for rows.Next() {
		var m Message
		var timestamp string
		var stepIndex sql.NullInt64
		var taskID sql.NullString

		err := rows.Scan(&m.ID, &m.SessionID, &timestamp, &m.Role, &m.Content, &stepIndex, &taskID)
		if err != nil {
			continue
		}

		m.Timestamp, _ = time.Parse(time.RFC3339, timestamp)
		if stepIndex.Valid {
			idx := int(stepIndex.Int64)
			m.StepIndex = &idx
		}
		m.TaskID = taskID.String

		messages = append(messages, &m)
	}

	return messages, nil
}

func (d *Database) AddToolInvocation(t *ToolInvocation) error {
	argsJSON, _ := json.Marshal(t.Arguments)
	resultJSON, _ := json.Marshal(t.Result)

	var success int
	if t.Success {
		success = 1
	}

	_, err := d.db.Exec(`
		INSERT INTO tool_invocations (id, session_id, timestamp, tool_type, tool_name, arguments, result, success, duration_ms)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
	`, t.ID, t.SessionID, t.Timestamp.Format(time.RFC3339), t.ToolType, t.ToolName,
		string(argsJSON), string(resultJSON), success, t.DurationMs)
	return err
}

func (d *Database) GetToolInvocations(sessionID string) ([]*ToolInvocation, error) {
	rows, err := d.db.Query(`
		SELECT * FROM tool_invocations WHERE session_id = ? ORDER BY timestamp ASC
	`, sessionID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var invocations []*ToolInvocation
	for rows.Next() {
		var t ToolInvocation
		var timestamp, argsJSON string
		var resultJSON sql.NullString
		var success int

		err := rows.Scan(&t.ID, &t.SessionID, &timestamp, &t.ToolType, &t.ToolName,
			&argsJSON, &resultJSON, &success, &t.DurationMs)
		if err != nil {
			continue
		}

		t.Timestamp, _ = time.Parse(time.RFC3339, timestamp)
		t.Success = success == 1
		json.Unmarshal([]byte(argsJSON), &t.Arguments)
		if resultJSON.Valid {
			json.Unmarshal([]byte(resultJSON.String), &t.Result)
		}

		invocations = append(invocations, &t)
	}

	return invocations, nil
}

func (d *Database) SaveWorkflowState(w *WorkflowState) error {
	stepResultsJSON, _ := json.Marshal(w.StepResults)
	planJSON, _ := json.Marshal(w.Plan)
	outputsJSON, _ := json.Marshal(w.Outputs)

	_, err := d.db.Exec(`
		INSERT OR REPLACE INTO workflow_states (session_id, current_step, step_results, plan, outputs)
		VALUES (?, ?, ?, ?, ?)
	`, w.SessionID, w.CurrentStep, string(stepResultsJSON), string(planJSON), string(outputsJSON))
	return err
}

func (d *Database) GetWorkflowState(sessionID string) (*WorkflowState, error) {
	row := d.db.QueryRow(`SELECT * FROM workflow_states WHERE session_id = ?`, sessionID)

	var w WorkflowState
	var stepResultsJSON, outputsJSON string
	var planJSON sql.NullString

	err := row.Scan(&w.SessionID, &w.CurrentStep, &stepResultsJSON, &planJSON, &outputsJSON)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}

	json.Unmarshal([]byte(stepResultsJSON), &w.StepResults)
	json.Unmarshal([]byte(outputsJSON), &w.Outputs)
	if planJSON.Valid {
		json.Unmarshal([]byte(planJSON.String), &w.Plan)
	}

	return &w, nil
}

func (d *Database) GetInterruptedSessions() ([]*Session, error) {
	rows, err := d.db.Query(`
		SELECT * FROM sessions WHERE status IN (?, ?) ORDER BY updated_at DESC
	`, string(StatusActive), string(StatusInterrupted))
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var sessions []*Session
	for rows.Next() {
		var s Session
		var createdAt, updatedAt, statusStr, configJSON string
		var workflowName, name, autoName sql.NullString

		err := rows.Scan(&s.ID, &createdAt, &updatedAt, &statusStr, &workflowName,
			&s.InitialPrompt, &s.Cwd, &configJSON, &name, &autoName)
		if err != nil {
			continue
		}

		s.CreatedAt, _ = time.Parse(time.RFC3339, createdAt)
		s.UpdatedAt, _ = time.Parse(time.RFC3339, updatedAt)
		s.Status = Status(statusStr)
		s.WorkflowName = workflowName.String
		s.Name = name.String
		s.AutoName = autoName.String
		json.Unmarshal([]byte(configJSON), &s.ConfigSnapshot)

		sessions = append(sessions, &s)
	}

	return sessions, nil
}

func (d *Database) GetSessionInfo(sessionID string) (map[string]any, error) {
	session, err := d.GetSession(sessionID)
	if err != nil || session == nil {
		return nil, err
	}

	messages, _ := d.GetMessages(sessionID)
	invocations, _ := d.GetToolInvocations(sessionID)
	workflowState, _ := d.GetWorkflowState(sessionID)

	messagesSlice := make([]map[string]any, len(messages))
	for i, m := range messages {
		messagesSlice[i] = m.ToMap()
	}

	invocationsSlice := make([]map[string]any, len(invocations))
	for i, t := range invocations {
		invocationsSlice[i] = t.ToMap()
	}

	result := map[string]any{
		"session":          session.ToMap(),
		"messages":         messagesSlice,
		"tool_invocations": invocationsSlice,
	}

	if workflowState != nil {
		result["workflow_state"] = workflowState.ToMap()
	}

	return result, nil
}

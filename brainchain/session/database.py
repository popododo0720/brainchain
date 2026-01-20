"""
SQLite database operations for session management.

Provides CRUD operations for sessions, messages, and tool invocations.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from .models import Message, Session, SessionStatus, ToolInvocation, WorkflowState


# Schema version for migrations
SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    workflow_name TEXT,
    initial_prompt TEXT NOT NULL,
    cwd TEXT NOT NULL,
    config_snapshot TEXT NOT NULL
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    step_index INTEGER,
    task_id TEXT
);

-- Tool invocations table
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

-- Workflow states table
CREATE TABLE IF NOT EXISTS workflow_states (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    current_step INTEGER NOT NULL,
    step_results TEXT NOT NULL,
    plan TEXT,
    outputs TEXT NOT NULL
);

-- Schema metadata
CREATE TABLE IF NOT EXISTS schema_info (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_invocations_session ON tool_invocations(session_id);
"""


class SessionDatabase:
    """
    SQLite database wrapper for session persistence.

    Provides thread-safe database operations with context management.
    """

    def __init__(self, db_path: str | Path):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Initialize database schema if needed."""
        with self._connection() as conn:
            conn.executescript(SCHEMA_SQL)

            # Store schema version
            conn.execute(
                "INSERT OR REPLACE INTO schema_info (key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION))
            )
            conn.commit()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Get a database connection with proper cleanup."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    # Session operations

    def create_session(self, session: Session) -> None:
        """Insert a new session."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions
                (id, created_at, updated_at, status, workflow_name, initial_prompt, cwd, config_snapshot)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    session.status.value,
                    session.workflow_name,
                    session.initial_prompt,
                    session.cwd,
                    json.dumps(session.config_snapshot),
                ),
            )
            conn.commit()

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            return Session.from_row(row) if row else None

    def update_session_status(
        self,
        session_id: str,
        status: SessionStatus,
    ) -> None:
        """Update session status."""
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status.value, datetime.now().isoformat(), session_id),
            )
            conn.commit()

    def list_sessions(
        self,
        status: SessionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Session]:
        """List sessions with optional filtering."""
        with self._connection() as conn:
            if status:
                cursor = conn.execute(
                    """
                    SELECT * FROM sessions
                    WHERE status = ?
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (status.value, limit, offset),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM sessions
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )
            return [Session.from_row(row) for row in cursor.fetchall()]

    def delete_session(self, session_id: str) -> None:
        """Delete a session and all related data."""
        with self._connection() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()

    def cleanup_old_sessions(self, retention_days: int = 30) -> int:
        """Delete sessions older than retention period."""
        cutoff = datetime.now() - timedelta(days=retention_days)
        with self._connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM sessions
                WHERE updated_at < ? AND status IN (?, ?)
                """,
                (cutoff.isoformat(), SessionStatus.COMPLETED.value, SessionStatus.FAILED.value),
            )
            conn.commit()
            return cursor.rowcount

    # Message operations

    def add_message(self, message: Message) -> None:
        """Insert a new message."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO messages
                (id, session_id, timestamp, role, content, step_index, task_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.session_id,
                    message.timestamp.isoformat(),
                    message.role,
                    message.content,
                    message.step_index,
                    message.task_id,
                ),
            )
            conn.commit()

    def get_messages(self, session_id: str) -> list[Message]:
        """Get all messages for a session."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
                """,
                (session_id,),
            )
            return [Message.from_row(row) for row in cursor.fetchall()]

    # Tool invocation operations

    def add_tool_invocation(self, invocation: ToolInvocation) -> None:
        """Insert a new tool invocation."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO tool_invocations
                (id, session_id, timestamp, tool_type, tool_name, arguments, result, success, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invocation.id,
                    invocation.session_id,
                    invocation.timestamp.isoformat(),
                    invocation.tool_type,
                    invocation.tool_name,
                    json.dumps(invocation.arguments),
                    json.dumps(invocation.result) if invocation.result is not None else None,
                    1 if invocation.success else 0,
                    invocation.duration_ms,
                ),
            )
            conn.commit()

    def get_tool_invocations(self, session_id: str) -> list[ToolInvocation]:
        """Get all tool invocations for a session."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM tool_invocations
                WHERE session_id = ?
                ORDER BY timestamp ASC
                """,
                (session_id,),
            )
            return [ToolInvocation.from_row(row) for row in cursor.fetchall()]

    # Workflow state operations

    def save_workflow_state(self, state: WorkflowState) -> None:
        """Save or update workflow state."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO workflow_states
                (session_id, current_step, step_results, plan, outputs)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    state.session_id,
                    state.current_step,
                    json.dumps(state.step_results),
                    json.dumps(state.plan) if state.plan else None,
                    json.dumps(state.outputs),
                ),
            )
            conn.commit()

    def get_workflow_state(self, session_id: str) -> WorkflowState | None:
        """Get workflow state for a session."""
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_states WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            return WorkflowState.from_row(row) if row else None

    def get_interrupted_sessions(self) -> list[Session]:
        """Get sessions that were interrupted (for recovery)."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM sessions
                WHERE status IN (?, ?)
                ORDER BY updated_at DESC
                """,
                (SessionStatus.ACTIVE.value, SessionStatus.INTERRUPTED.value),
            )
            return [Session.from_row(row) for row in cursor.fetchall()]

    def get_session_info(self, session_id: str) -> dict[str, Any] | None:
        """Get complete session information including messages and invocations."""
        session = self.get_session(session_id)
        if not session:
            return None

        messages = self.get_messages(session_id)
        invocations = self.get_tool_invocations(session_id)
        workflow_state = self.get_workflow_state(session_id)

        return {
            "session": session.to_dict(),
            "messages": [m.to_dict() for m in messages],
            "tool_invocations": [i.to_dict() for i in invocations],
            "workflow_state": workflow_state.to_dict() if workflow_state else None,
        }

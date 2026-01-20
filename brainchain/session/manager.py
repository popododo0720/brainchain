"""
Session manager for Brainchain.

Provides high-level session management operations.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ..compat import get_config_dir
from .database import SessionDatabase
from .models import Message, Session, SessionStatus, ToolInvocation, WorkflowState


def get_default_db_path() -> Path:
    """Get default database path."""
    return get_config_dir() / "sessions.db"


class SessionManager:
    """
    High-level session management interface.

    Manages the complete lifecycle of sessions including:
    - Session creation and tracking
    - Message recording
    - Tool invocation logging
    - Workflow state persistence
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        enabled: bool = True,
        auto_save: bool = True,
    ):
        """
        Initialize session manager.

        Args:
            db_path: Path to database file (defaults to config dir)
            enabled: Whether session tracking is enabled
            auto_save: Whether to auto-save state changes
        """
        self.enabled = enabled
        self.auto_save = auto_save
        self._current_session_id: str | None = None

        if enabled:
            self._db = SessionDatabase(db_path or get_default_db_path())
        else:
            self._db = None

    @property
    def current_session(self) -> Session | None:
        """Get the current active session."""
        if not self._db or not self._current_session_id:
            return None
        return self._db.get_session(self._current_session_id)

    def create_session(
        self,
        initial_prompt: str,
        cwd: str | Path,
        workflow_name: str | None = None,
        config_snapshot: dict[str, Any] | None = None,
    ) -> Session | None:
        """
        Create a new session.

        Args:
            initial_prompt: Initial user prompt
            cwd: Working directory
            workflow_name: Optional workflow name
            config_snapshot: Optional config snapshot for reproducibility

        Returns:
            Created Session or None if disabled
        """
        if not self._db:
            return None

        now = datetime.now()
        session = Session(
            id=str(uuid.uuid4()),
            created_at=now,
            updated_at=now,
            status=SessionStatus.ACTIVE,
            workflow_name=workflow_name,
            initial_prompt=initial_prompt,
            cwd=str(cwd),
            config_snapshot=config_snapshot or {},
        )

        self._db.create_session(session)
        self._current_session_id = session.id
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        if not self._db:
            return None
        return self._db.get_session(session_id)

    def update_status(self, session_id: str, status: SessionStatus) -> None:
        """Update session status."""
        if not self._db:
            return
        self._db.update_session_status(session_id, status)

    def complete_session(self, session_id: str | None = None) -> None:
        """Mark session as completed."""
        sid = session_id or self._current_session_id
        if sid:
            self.update_status(sid, SessionStatus.COMPLETED)
            if sid == self._current_session_id:
                self._current_session_id = None

    def fail_session(self, session_id: str | None = None, error: str | None = None) -> None:
        """Mark session as failed."""
        sid = session_id or self._current_session_id
        if sid:
            self.update_status(sid, SessionStatus.FAILED)
            if error:
                self.add_message(sid, "system", f"Session failed: {error}")
            if sid == self._current_session_id:
                self._current_session_id = None

    def interrupt_session(self, session_id: str | None = None) -> None:
        """Mark session as interrupted (for recovery)."""
        sid = session_id or self._current_session_id
        if sid:
            self.update_status(sid, SessionStatus.INTERRUPTED)

    def list_sessions(
        self,
        status: SessionStatus | None = None,
        limit: int = 50,
    ) -> list[Session]:
        """List sessions with optional status filter."""
        if not self._db:
            return []
        return self._db.list_sessions(status=status, limit=limit)

    def get_session_info(self, session_id: str) -> dict[str, Any] | None:
        """Get complete session information."""
        if not self._db:
            return None
        return self._db.get_session_info(session_id)

    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        if not self._db:
            return
        self._db.delete_session(session_id)

    def cleanup_old_sessions(self, retention_days: int = 30) -> int:
        """Clean up old completed/failed sessions."""
        if not self._db:
            return 0
        return self._db.cleanup_old_sessions(retention_days)

    # Message operations

    def add_message(
        self,
        session_id: str | None,
        role: str,
        content: str,
        step_index: int | None = None,
        task_id: str | None = None,
    ) -> Message | None:
        """
        Add a message to a session.

        Args:
            session_id: Session ID (or current session if None)
            role: Message role (user, assistant, system)
            content: Message content
            step_index: Optional workflow step index
            task_id: Optional task ID

        Returns:
            Created Message or None
        """
        if not self._db:
            return None

        sid = session_id or self._current_session_id
        if not sid:
            return None

        message = Message(
            id=str(uuid.uuid4()),
            session_id=sid,
            timestamp=datetime.now(),
            role=role,
            content=content,
            step_index=step_index,
            task_id=task_id,
        )

        self._db.add_message(message)
        return message

    def get_messages(self, session_id: str | None = None) -> list[Message]:
        """Get all messages for a session."""
        if not self._db:
            return []
        sid = session_id or self._current_session_id
        if not sid:
            return []
        return self._db.get_messages(sid)

    # Tool invocation operations

    def record_tool_invocation(
        self,
        session_id: str | None,
        tool_type: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any = None,
        success: bool = False,
        duration_ms: int = 0,
    ) -> ToolInvocation | None:
        """
        Record a tool invocation.

        Args:
            session_id: Session ID (or current session if None)
            tool_type: Type of tool (lsp, mcp, cli)
            tool_name: Name of the tool
            arguments: Tool arguments
            result: Tool result
            success: Whether invocation succeeded
            duration_ms: Duration in milliseconds

        Returns:
            Created ToolInvocation or None
        """
        if not self._db:
            return None

        sid = session_id or self._current_session_id
        if not sid:
            return None

        invocation = ToolInvocation(
            id=str(uuid.uuid4()),
            session_id=sid,
            timestamp=datetime.now(),
            tool_type=tool_type,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            success=success,
            duration_ms=duration_ms,
        )

        self._db.add_tool_invocation(invocation)
        return invocation

    def get_tool_invocations(self, session_id: str | None = None) -> list[ToolInvocation]:
        """Get all tool invocations for a session."""
        if not self._db:
            return []
        sid = session_id or self._current_session_id
        if not sid:
            return []
        return self._db.get_tool_invocations(sid)

    # Workflow state operations

    def save_workflow_state(
        self,
        session_id: str | None,
        current_step: int,
        step_results: list[dict[str, Any]],
        plan: dict[str, Any] | None = None,
        outputs: dict[str, str] | None = None,
    ) -> WorkflowState | None:
        """
        Save workflow state for resume capability.

        Args:
            session_id: Session ID (or current session if None)
            current_step: Current workflow step index
            step_results: Results from completed steps
            plan: Parsed plan data
            outputs: Step outputs

        Returns:
            Created WorkflowState or None
        """
        if not self._db:
            return None

        sid = session_id or self._current_session_id
        if not sid:
            return None

        state = WorkflowState(
            session_id=sid,
            current_step=current_step,
            step_results=step_results,
            plan=plan,
            outputs=outputs or {},
        )

        self._db.save_workflow_state(state)
        return state

    def get_workflow_state(self, session_id: str | None = None) -> WorkflowState | None:
        """Get workflow state for a session."""
        if not self._db:
            return None
        sid = session_id or self._current_session_id
        if not sid:
            return None
        return self._db.get_workflow_state(sid)

    def get_interrupted_sessions(self) -> list[Session]:
        """Get sessions that can be resumed."""
        if not self._db:
            return []
        return self._db.get_interrupted_sessions()

    def set_current_session(self, session_id: str) -> bool:
        """Set the current active session."""
        if not self._db:
            return False
        session = self._db.get_session(session_id)
        if session:
            self._current_session_id = session_id
            return True
        return False

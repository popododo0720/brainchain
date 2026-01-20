"""
Session management for Brainchain.

Provides session persistence, state tracking, and crash recovery.

Features:
- SQLite-based session storage
- Message and tool invocation tracking
- Workflow state persistence
- Automatic crash recovery

Usage:
    from brainchain.session import SessionManager, Session

    manager = SessionManager()
    session = manager.create_session(prompt="My task", cwd="/path")
    manager.add_message(session.id, "user", "Hello")
    manager.update_status(session.id, SessionStatus.COMPLETED)
"""

from .models import Session, Message, ToolInvocation, WorkflowState, SessionStatus
from .manager import SessionManager
from .recovery import RecoveryManager

__all__ = [
    "Session",
    "Message",
    "ToolInvocation",
    "WorkflowState",
    "SessionStatus",
    "SessionManager",
    "RecoveryManager",
]

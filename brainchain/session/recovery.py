"""
Crash recovery for Brainchain sessions.

Provides automatic detection and recovery of interrupted sessions.
"""

from datetime import datetime, timedelta
from typing import Any

from .manager import SessionManager
from .models import Session, SessionStatus, WorkflowState


class RecoveryManager:
    """
    Manages crash detection and session recovery.

    Features:
    - Automatic detection of interrupted sessions
    - Workflow state restoration
    - Graceful resume prompting
    """

    def __init__(
        self,
        session_manager: SessionManager,
        auto_detect: bool = True,
        prompt_resume: bool = True,
    ):
        """
        Initialize recovery manager.

        Args:
            session_manager: SessionManager instance
            auto_detect: Whether to automatically detect crashed sessions
            prompt_resume: Whether to prompt user for resume
        """
        self.session_manager = session_manager
        self.auto_detect = auto_detect
        self.prompt_resume = prompt_resume

    def check_for_recovery(self) -> list[Session]:
        """
        Check for sessions that can be recovered.

        Returns:
            List of recoverable sessions
        """
        if not self.auto_detect:
            return []
        return self.session_manager.get_interrupted_sessions()

    def get_recovery_info(self, session: Session) -> dict[str, Any]:
        """
        Get detailed recovery information for a session.

        Args:
            session: Session to get info for

        Returns:
            Dictionary with recovery details
        """
        workflow_state = self.session_manager.get_workflow_state(session.id)
        messages = self.session_manager.get_messages(session.id)

        return {
            "session_id": session.id,
            "initial_prompt": session.initial_prompt,
            "workflow_name": session.workflow_name,
            "cwd": session.cwd,
            "status": session.status.value,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "current_step": workflow_state.current_step if workflow_state else 0,
            "completed_steps": len(workflow_state.step_results) if workflow_state else 0,
            "message_count": len(messages),
            "has_plan": bool(workflow_state and workflow_state.plan),
        }

    def prepare_resume(self, session_id: str) -> dict[str, Any] | None:
        """
        Prepare session state for resume.

        Args:
            session_id: Session ID to resume

        Returns:
            State dict for resume or None if not found
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            return None

        workflow_state = self.session_manager.get_workflow_state(session_id)

        # Update session status to active
        self.session_manager.update_status(session_id, SessionStatus.ACTIVE)
        self.session_manager.set_current_session(session_id)

        return {
            "session": session,
            "workflow_state": workflow_state,
            "initial_prompt": session.initial_prompt,
            "cwd": session.cwd,
            "config_snapshot": session.config_snapshot,
            "resume_from_step": workflow_state.current_step if workflow_state else 0,
            "plan": workflow_state.plan if workflow_state else None,
            "outputs": workflow_state.outputs if workflow_state else {},
        }

    def mark_for_recovery(self, session_id: str) -> None:
        """
        Mark a session as interrupted for later recovery.

        Args:
            session_id: Session ID to mark
        """
        self.session_manager.interrupt_session(session_id)

    def cleanup_stale_sessions(self, stale_hours: int = 24) -> int:
        """
        Clean up sessions that have been interrupted for too long.

        Args:
            stale_hours: Hours after which interrupted sessions are considered stale

        Returns:
            Number of sessions cleaned up
        """
        interrupted = self.session_manager.get_interrupted_sessions()
        cutoff = datetime.now() - timedelta(hours=stale_hours)

        cleaned = 0
        for session in interrupted:
            if session.updated_at < cutoff:
                self.session_manager.update_status(session.id, SessionStatus.FAILED)
                self.session_manager.add_message(
                    session.id,
                    "system",
                    f"Session marked as failed after being interrupted for {stale_hours}+ hours"
                )
                cleaned += 1

        return cleaned

    def format_recovery_prompt(self, sessions: list[Session]) -> str:
        """
        Format a user-friendly recovery prompt.

        Args:
            sessions: List of recoverable sessions

        Returns:
            Formatted prompt string
        """
        if not sessions:
            return ""

        lines = ["Found interrupted sessions that can be resumed:\n"]

        for i, session in enumerate(sessions[:5], 1):  # Limit to 5
            info = self.get_recovery_info(session)
            prompt_preview = session.initial_prompt[:50]
            if len(session.initial_prompt) > 50:
                prompt_preview += "..."

            lines.append(f"  {i}. [{session.id[:8]}] \"{prompt_preview}\"")
            lines.append(f"     Status: {info['status']}, Step: {info['current_step']}, Messages: {info['message_count']}")
            lines.append(f"     Updated: {info['updated_at']}")
            lines.append("")

        lines.append("Use --resume <session_id> to continue a session.")

        return "\n".join(lines)

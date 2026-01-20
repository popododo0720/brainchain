"""
Data models for session management.

Defines the core data structures for sessions, messages, and tool invocations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import json


class SessionStatus(Enum):
    """Status of a session."""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass
class Session:
    """
    Represents a brainchain session.

    Tracks the complete lifecycle of a workflow execution.
    """
    id: str
    created_at: datetime
    updated_at: datetime
    status: SessionStatus
    workflow_name: str | None
    initial_prompt: str
    cwd: str
    config_snapshot: dict[str, Any]
    # Session naming fields
    name: str | None = None          # User-specified name
    auto_name: str | None = None     # Auto-generated name from prompt

    @property
    def display_name(self) -> str:
        """Get display name with priority: name > auto_name > id[:8]."""
        return self.name or self.auto_name or self.id[:8]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "workflow_name": self.workflow_name,
            "initial_prompt": self.initial_prompt,
            "cwd": self.cwd,
            "config_snapshot": self.config_snapshot,
            "name": self.name,
            "auto_name": self.auto_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """Create Session from dictionary."""
        return cls(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            status=SessionStatus(data["status"]),
            workflow_name=data.get("workflow_name"),
            initial_prompt=data["initial_prompt"],
            cwd=data["cwd"],
            config_snapshot=data.get("config_snapshot", {}),
            name=data.get("name"),
            auto_name=data.get("auto_name"),
        )

    @classmethod
    def from_row(cls, row: tuple) -> "Session":
        """Create Session from database row."""
        return cls(
            id=row[0],
            created_at=datetime.fromisoformat(row[1]),
            updated_at=datetime.fromisoformat(row[2]),
            status=SessionStatus(row[3]),
            workflow_name=row[4],
            initial_prompt=row[5],
            cwd=row[6],
            config_snapshot=json.loads(row[7]) if row[7] else {},
            name=row[8] if len(row) > 8 else None,
            auto_name=row[9] if len(row) > 9 else None,
        )


@dataclass
class Message:
    """
    Represents a message in a session.

    Messages can be from user, assistant, or system.
    """
    id: str
    session_id: str
    timestamp: datetime
    role: str  # user, assistant, system
    content: str
    step_index: int | None = None
    task_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "role": self.role,
            "content": self.content,
            "step_index": self.step_index,
            "task_id": self.task_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Create Message from dictionary."""
        return cls(
            id=data["id"],
            session_id=data["session_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            role=data["role"],
            content=data["content"],
            step_index=data.get("step_index"),
            task_id=data.get("task_id"),
        )

    @classmethod
    def from_row(cls, row: tuple) -> "Message":
        """Create Message from database row."""
        return cls(
            id=row[0],
            session_id=row[1],
            timestamp=datetime.fromisoformat(row[2]),
            role=row[3],
            content=row[4],
            step_index=row[5],
            task_id=row[6],
        )


@dataclass
class ToolInvocation:
    """
    Represents a tool invocation in a session.

    Tracks calls to LSP, MCP, or CLI tools.
    """
    id: str
    session_id: str
    timestamp: datetime
    tool_type: str  # lsp, mcp, cli
    tool_name: str
    arguments: dict[str, Any]
    result: Any = None
    success: bool = False
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "tool_type": self.tool_type,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
            "success": self.success,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolInvocation":
        """Create ToolInvocation from dictionary."""
        return cls(
            id=data["id"],
            session_id=data["session_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            tool_type=data["tool_type"],
            tool_name=data["tool_name"],
            arguments=data.get("arguments", {}),
            result=data.get("result"),
            success=data.get("success", False),
            duration_ms=data.get("duration_ms", 0),
        )

    @classmethod
    def from_row(cls, row: tuple) -> "ToolInvocation":
        """Create ToolInvocation from database row."""
        return cls(
            id=row[0],
            session_id=row[1],
            timestamp=datetime.fromisoformat(row[2]),
            tool_type=row[3],
            tool_name=row[4],
            arguments=json.loads(row[5]) if row[5] else {},
            result=json.loads(row[6]) if row[6] else None,
            success=bool(row[7]),
            duration_ms=row[8],
        )


@dataclass
class WorkflowState:
    """
    Represents the state of a workflow execution.

    Used for resuming interrupted workflows.
    """
    session_id: str
    current_step: int
    step_results: list[dict[str, Any]] = field(default_factory=list)
    plan: dict[str, Any] | None = None
    outputs: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "current_step": self.current_step,
            "step_results": self.step_results,
            "plan": self.plan,
            "outputs": self.outputs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowState":
        """Create WorkflowState from dictionary."""
        return cls(
            session_id=data["session_id"],
            current_step=data["current_step"],
            step_results=data.get("step_results", []),
            plan=data.get("plan"),
            outputs=data.get("outputs", {}),
        )

    @classmethod
    def from_row(cls, row: tuple) -> "WorkflowState":
        """Create WorkflowState from database row."""
        return cls(
            session_id=row[0],
            current_step=row[1],
            step_results=json.loads(row[2]) if row[2] else [],
            plan=json.loads(row[3]) if row[3] else None,
            outputs=json.loads(row[4]) if row[4] else {},
        )

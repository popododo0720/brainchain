"""
Custom exceptions for Brainchain.

All brainchain-specific errors inherit from BrainchainError.
"""

__all__ = [
    "BrainchainError",
    # Config errors
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigValidationError",
    "PromptNotFoundError",
    # Execution errors
    "ExecutionError",
    "TaskTimeoutError",
    "RoleNotFoundError",
    # Workflow errors
    "WorkflowError",
    "WorkflowStepError",
    "WorkflowJumpError",
    # Session errors
    "SessionError",
    "SessionNotFoundError",
    "SessionRecoveryError",
    # MCP errors
    "MCPError",
    "MCPConnectionError",
    "MCPToolError",
    # LSP errors
    "LSPError",
    "LSPConnectionError",
    "LSPOperationError",
]


class BrainchainError(Exception):
    """Base exception for all brainchain errors."""

    def __init__(self, message: str, details: str | None = None):
        self.message = message
        self.details = details
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}\n  Details: {self.details}"
        return self.message


# Configuration Errors

class ConfigError(BrainchainError):
    """Base class for configuration errors."""
    pass


class ConfigNotFoundError(ConfigError):
    """Raised when config file is not found."""

    def __init__(self, path: str):
        super().__init__(
            f"Configuration file not found: {path}",
            details="Run 'brainchain --init' to initialize configuration"
        )
        self.path = path


class ConfigValidationError(ConfigError):
    """Raised when config validation fails."""

    def __init__(self, message: str, field: str | None = None):
        details = f"Field: {field}" if field else None
        super().__init__(f"Configuration validation error: {message}", details)
        self.field = field


class PromptNotFoundError(ConfigError):
    """Raised when a prompt file is not found."""

    def __init__(self, role: str, path: str):
        super().__init__(
            f"Prompt file not found for role '{role}': {path}"
        )
        self.role = role
        self.path = path


# Execution Errors

class ExecutionError(BrainchainError):
    """Base class for execution errors."""
    pass


class TaskTimeoutError(ExecutionError):
    """Raised when a task exceeds its timeout."""

    def __init__(self, task_id: str | None, timeout: int):
        super().__init__(
            f"Task timed out after {timeout} seconds",
            details=f"Task ID: {task_id}" if task_id else None
        )
        self.task_id = task_id
        self.timeout = timeout


class RoleNotFoundError(ExecutionError):
    """Raised when an unknown role is requested."""

    def __init__(self, role: str, available_roles: list[str]):
        super().__init__(
            f"Unknown role: '{role}'",
            details=f"Available roles: {', '.join(available_roles)}"
        )
        self.role = role
        self.available_roles = available_roles


# Workflow Errors

class WorkflowError(BrainchainError):
    """Base class for workflow errors."""
    pass


class WorkflowStepError(WorkflowError):
    """Raised when a workflow step fails."""

    def __init__(self, step_index: int, role: str, message: str):
        super().__init__(
            f"Workflow step {step_index + 1} ({role}) failed: {message}"
        )
        self.step_index = step_index
        self.role = role


class WorkflowJumpError(WorkflowError):
    """Raised when a workflow jump target is invalid."""

    def __init__(self, target: str, available_roles: list[str]):
        super().__init__(
            f"Invalid workflow jump target: '{target}'",
            details=f"Available roles: {', '.join(available_roles)}"
        )
        self.target = target
        self.available_roles = available_roles


# Session Errors

class SessionError(BrainchainError):
    """Base class for session errors."""
    pass


class SessionNotFoundError(SessionError):
    """Raised when a session is not found."""

    def __init__(self, session_id: str):
        super().__init__(
            f"Session not found: {session_id}",
            details="The session may have been deleted or expired"
        )
        self.session_id = session_id


class SessionRecoveryError(SessionError):
    """Raised when session recovery fails."""

    def __init__(self, session_id: str, reason: str):
        super().__init__(
            f"Failed to recover session: {session_id}",
            details=reason
        )
        self.session_id = session_id
        self.reason = reason


# MCP Errors

class MCPError(BrainchainError):
    """Base class for MCP errors."""
    pass


class MCPConnectionError(MCPError):
    """Raised when MCP server connection fails."""

    def __init__(self, server_name: str, reason: str | None = None):
        super().__init__(
            f"Failed to connect to MCP server: {server_name}",
            details=reason
        )
        self.server_name = server_name
        self.reason = reason


class MCPToolError(MCPError):
    """Raised when an MCP tool invocation fails."""

    def __init__(self, tool_name: str, reason: str | None = None):
        super().__init__(
            f"MCP tool error: {tool_name}",
            details=reason
        )
        self.tool_name = tool_name
        self.reason = reason


# LSP Errors

class LSPError(BrainchainError):
    """Base class for LSP errors."""
    pass


class LSPConnectionError(LSPError):
    """Raised when LSP server connection fails."""

    def __init__(self, server_name: str, reason: str | None = None):
        super().__init__(
            f"Failed to connect to LSP server: {server_name}",
            details=reason
        )
        self.server_name = server_name
        self.reason = reason


class LSPOperationError(LSPError):
    """Raised when an LSP operation fails."""

    def __init__(self, operation: str, reason: str | None = None):
        super().__init__(
            f"LSP operation failed: {operation}",
            details=reason
        )
        self.operation = operation
        self.reason = reason

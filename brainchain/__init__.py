"""
Brainchain - Multi-CLI AI Orchestrator with workflow automation.

A framework for orchestrating multiple AI CLI agents to work together
on complex software development tasks.

Features:
- Role-based agent delegation (planner, implementer, reviewer, etc.)
- Automatic workflow execution (Plan → Validate → Implement → Review)
- Parallel task execution with progress display
- Cross-platform support (Linux, macOS, Windows)
- Retry logic with configurable policy
- Session management with crash recovery
- MCP integration for external tools
- LSP/AST tools for semantic code analysis

Example usage:
    # CLI
    $ brainchain --workflow "Create user authentication"
    $ brainchain --exec planner "Design API endpoints"
    $ brainchain --parallel tasks.json
    $ brainchain --sessions  # List sessions
    $ brainchain --resume <session_id>  # Resume interrupted session
    $ brainchain --mcp-list  # List MCP tools
    $ brainchain --lsp refs file.py MyClass  # Find references

    # Python API
    from brainchain import WorkflowEngine, load_config, load_prompts
    from brainchain.session import SessionManager
    from brainchain.mcp import ToolRegistry  # requires uv add brainchain[mcp]
    from brainchain.lsp import LSPOperations  # requires uv add brainchain[lsp]

    config = load_config()
    prompts = load_prompts(config)
    # ... use components
"""

__version__ = "0.3.0"
__author__ = "Brainchain Contributors"

# Core components
from .config import (
    load_config,
    load_prompts,
    init_config,
    build_system_context,
    get_session_config,
    get_mcp_config,
    get_lsp_config,
)
from .executor import Executor, TaskResult
from .workflow import WorkflowEngine, WorkflowResult, StepResult
from .ui import ProgressUI, Colors, Symbols
from .exceptions import (
    BrainchainError,
    ConfigError,
    ConfigNotFoundError,
    ConfigValidationError,
    PromptNotFoundError,
    ExecutionError,
    TaskTimeoutError,
    RoleNotFoundError,
    WorkflowError,
    WorkflowStepError,
    WorkflowJumpError,
    # Session errors
    SessionError,
    SessionNotFoundError,
    SessionRecoveryError,
    # MCP errors
    MCPError,
    MCPConnectionError,
    MCPToolError,
    # LSP errors
    LSPError,
    LSPConnectionError,
    LSPOperationError,
)
from .compat import (
    get_config_dir,
    supports_color,
    supports_unicode,
)

# Session management (always available, uses stdlib sqlite3)
from .session import (
    SessionManager,
    RecoveryManager,
    Session,
    SessionStatus,
    Message,
    ToolInvocation,
    WorkflowState,
)

__all__ = [
    # Version
    "__version__",
    # Config
    "load_config",
    "load_prompts",
    "init_config",
    "build_system_context",
    "get_session_config",
    "get_mcp_config",
    "get_lsp_config",
    # Execution
    "Executor",
    "TaskResult",
    # Workflow
    "WorkflowEngine",
    "WorkflowResult",
    "StepResult",
    # UI
    "ProgressUI",
    "Colors",
    "Symbols",
    # Session management
    "SessionManager",
    "RecoveryManager",
    "Session",
    "SessionStatus",
    "Message",
    "ToolInvocation",
    "WorkflowState",
    # Exceptions - Base
    "BrainchainError",
    # Exceptions - Config
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigValidationError",
    "PromptNotFoundError",
    # Exceptions - Execution
    "ExecutionError",
    "TaskTimeoutError",
    "RoleNotFoundError",
    # Exceptions - Workflow
    "WorkflowError",
    "WorkflowStepError",
    "WorkflowJumpError",
    # Exceptions - Session
    "SessionError",
    "SessionNotFoundError",
    "SessionRecoveryError",
    # Exceptions - MCP
    "MCPError",
    "MCPConnectionError",
    "MCPToolError",
    # Exceptions - LSP
    "LSPError",
    "LSPConnectionError",
    "LSPOperationError",
    # Compat
    "get_config_dir",
    "supports_color",
    "supports_unicode",
]

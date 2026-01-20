"""
MCP (Model Context Protocol) integration for Brainchain.

Provides external tool integration through the MCP protocol.

Features:
- MCP server connection management
- Tool registry and discovery
- Prompt injection for tool descriptions
- Built-in server configurations

Usage:
    from brainchain.mcp import MCPClient, ToolRegistry, PromptInjector

    registry = ToolRegistry()
    client = MCPClient(config)
    await client.connect()
    registry.register_client("filesystem", client)

    tools = registry.get_all_tools()
    result = await registry.call_tool("filesystem_read", {"path": "file.txt"})

Note: Requires optional dependency: uv add brainchain[mcp]
"""

from typing import TYPE_CHECKING

# Lazy imports to avoid requiring MCP dependency for core functionality
_mcp_available: bool | None = None


def is_mcp_available() -> bool:
    """Check if MCP dependencies are available."""
    global _mcp_available
    if _mcp_available is None:
        try:
            import mcp  # noqa: F401
            _mcp_available = True
        except ImportError:
            _mcp_available = False
    return _mcp_available


def _check_mcp_dependency() -> None:
    """Raise helpful error if MCP is not installed."""
    if not is_mcp_available():
        raise ImportError(
            "MCP support requires the 'mcp' package. "
            "Install it with: uv add brainchain[mcp]"
        )


# Type-only imports for IDE support
if TYPE_CHECKING:
    from .client import MCPClient
    from .registry import ToolRegistry, Tool, ToolResult
    from .prompt_injection import PromptInjector, ToolCall
    from .servers import MCPServerConfig, BUILTIN_SERVERS


def __getattr__(name: str):
    """Lazy import MCP components."""
    _check_mcp_dependency()

    if name == "MCPClient":
        from .client import MCPClient
        return MCPClient
    elif name == "ToolRegistry":
        from .registry import ToolRegistry
        return ToolRegistry
    elif name == "Tool":
        from .registry import Tool
        return Tool
    elif name == "ToolResult":
        from .registry import ToolResult
        return ToolResult
    elif name == "PromptInjector":
        from .prompt_injection import PromptInjector
        return PromptInjector
    elif name == "ToolCall":
        from .prompt_injection import ToolCall
        return ToolCall
    elif name == "MCPServerConfig":
        from .servers import MCPServerConfig
        return MCPServerConfig
    elif name == "BUILTIN_SERVERS":
        from .servers import BUILTIN_SERVERS
        return BUILTIN_SERVERS
    else:
        raise AttributeError(f"module 'brainchain.mcp' has no attribute '{name}'")


__all__ = [
    "is_mcp_available",
    "MCPClient",
    "ToolRegistry",
    "Tool",
    "ToolResult",
    "PromptInjector",
    "ToolCall",
    "MCPServerConfig",
    "BUILTIN_SERVERS",
]

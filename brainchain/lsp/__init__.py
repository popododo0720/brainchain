"""
LSP (Language Server Protocol) integration for Brainchain.

Provides semantic code analysis through LSP and AST tools.

Features:
- LSP server connection management
- Go to definition, find references, rename
- AST-based code search and transformation
- Multi-language support (Python, TypeScript)

Usage:
    from brainchain.lsp import LSPClient, LSPOperations, ASTTools

    async with LSPClient(config) as client:
        refs = await client.text_document_references(uri, line, char)

    ops = LSPOperations(client)
    refs = ops.find_references("file.py", "MyClass")

    ast = ASTTools()
    matches = ast.search("def $_($$$)", "src/")

Note: Requires optional dependency: uv add brainchain[lsp]
"""

from typing import TYPE_CHECKING

# Lazy imports to avoid requiring LSP dependency for core functionality
_lsp_available: bool | None = None
_ast_available: bool | None = None


def is_lsp_available() -> bool:
    """Check if LSP dependencies (pygls) are available."""
    global _lsp_available
    if _lsp_available is None:
        try:
            import pygls  # noqa: F401
            _lsp_available = True
        except ImportError:
            _lsp_available = False
    return _lsp_available


def is_ast_available() -> bool:
    """Check if AST dependencies (ast-grep-py) are available."""
    global _ast_available
    if _ast_available is None:
        try:
            import ast_grep_py  # noqa: F401
            _ast_available = True
        except ImportError:
            _ast_available = False
    return _ast_available


def _check_lsp_dependency() -> None:
    """Raise helpful error if LSP dependencies are not installed."""
    if not is_lsp_available():
        raise ImportError(
            "LSP support requires the 'pygls' package. "
            "Install it with: uv add brainchain[lsp]"
        )


def _check_ast_dependency() -> None:
    """Raise helpful error if AST dependencies are not installed."""
    if not is_ast_available():
        raise ImportError(
            "AST tools require the 'ast-grep-py' package. "
            "Install it with: uv add brainchain[lsp]"
        )


# Type-only imports for IDE support
if TYPE_CHECKING:
    from .client import LSPClient, Location, Diagnostic, WorkspaceEdit
    from .servers import LSPServerConfig, BUILTIN_SERVERS
    from .operations import LSPOperations
    from .ast_tools import ASTTools, Match, Change


def __getattr__(name: str):
    """Lazy import LSP components."""
    if name in ("LSPClient", "Location", "Diagnostic", "WorkspaceEdit"):
        _check_lsp_dependency()
        from .client import LSPClient, Location, Diagnostic, WorkspaceEdit
        return {"LSPClient": LSPClient, "Location": Location, "Diagnostic": Diagnostic, "WorkspaceEdit": WorkspaceEdit}[name]
    elif name == "LSPServerConfig":
        from .servers import LSPServerConfig
        return LSPServerConfig
    elif name == "BUILTIN_SERVERS":
        from .servers import BUILTIN_SERVERS
        return BUILTIN_SERVERS
    elif name == "LSPOperations":
        _check_lsp_dependency()
        from .operations import LSPOperations
        return LSPOperations
    elif name in ("ASTTools", "Match", "Change"):
        _check_ast_dependency()
        from .ast_tools import ASTTools, Match, Change
        return {"ASTTools": ASTTools, "Match": Match, "Change": Change}[name]
    else:
        raise AttributeError(f"module 'brainchain.lsp' has no attribute '{name}'")


__all__ = [
    "is_lsp_available",
    "is_ast_available",
    "LSPClient",
    "Location",
    "Diagnostic",
    "WorkspaceEdit",
    "LSPServerConfig",
    "BUILTIN_SERVERS",
    "LSPOperations",
    "ASTTools",
    "Match",
    "Change",
]

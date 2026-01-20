"""
CLI Adapters for various AI coding agents.

Adapters connect to external CLI tools via subprocess:
- Claude Code (claude)
- Aider (aider)
- Codex CLI (codex)
- OpenCode (opencode)
"""

from .base import BaseAdapter, AdapterConfig, AdapterResult
from .registry import AdapterRegistry

__all__ = [
    "BaseAdapter",
    "AdapterConfig",
    "AdapterResult",
    "AdapterRegistry",
]

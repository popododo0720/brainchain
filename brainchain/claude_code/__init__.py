"""
Claude Code integration for Brainchain.

Provides UI components that overlay on Claude Code output:
- Top bar status display
- Sidebar session list
- Output hooks and wrappers
"""

from .top_bar import TopBar
from .hooks import ClaudeCodeHooks, UIMode

__all__ = [
    "TopBar",
    "ClaudeCodeHooks",
    "UIMode",
]

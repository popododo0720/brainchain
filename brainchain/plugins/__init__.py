"""
Brainchain Plugin System.

Provides extensibility through:
- Custom commands (/command)
- Lifecycle hooks (pre/post execution)
- Event handlers
"""

from .loader import PluginLoader, PluginManager
from .commands import CommandRegistry, Command, command
from .hooks import HookRegistry, Hook, HookType

__all__ = [
    "PluginLoader",
    "PluginManager",
    "CommandRegistry",
    "Command",
    "command",
    "HookRegistry",
    "Hook",
    "HookType",
]

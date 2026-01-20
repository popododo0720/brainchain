"""
Hello Plugin - Example plugin for Brainchain.

This plugin demonstrates how to:
1. Register custom commands
2. Register lifecycle hooks
3. Integrate with brainchain

To install:
    Copy this folder to ~/.config/brainchain/plugins/
    or ./brainchain_plugins/
"""

# Plugin metadata (required)
name = "hello_plugin"
version = "1.0.0"
description = "Example plugin that adds /hello command and logging hooks"
author = "Brainchain Contributors"


def setup(manager):
    """
    Called when the plugin is loaded.

    Args:
        manager: PluginManager instance with access to:
            - manager.commands: CommandRegistry
            - manager.hooks: HookRegistry
            - manager.adapters: AdapterRegistry
    """
    # Register commands
    if manager.commands:
        from .commands import register_commands
        register_commands(manager.commands)

    # Register hooks
    if manager.hooks:
        from .hooks import register_hooks
        register_hooks(manager.hooks)

    print(f"[{name}] Plugin loaded successfully!")


def teardown(manager):
    """
    Called when the plugin is unloaded.

    Clean up any resources here.
    """
    print(f"[{name}] Plugin unloaded.")

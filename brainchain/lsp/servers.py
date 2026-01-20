"""
Built-in LSP server configurations.

Provides pre-configured server settings for common language servers.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LSPServerConfig:
    """Configuration for an LSP server."""
    command: list[str]
    name: str = ""
    file_patterns: list[str] = field(default_factory=list)
    language_id: str = ""
    init_options: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    auto_start: bool = False


# Built-in server configurations
BUILTIN_SERVERS: dict[str, LSPServerConfig] = {
    "python": LSPServerConfig(
        name="python",
        command=["pylsp"],
        file_patterns=["*.py"],
        language_id="python",
        init_options={},
        settings={
            "pylsp": {
                "plugins": {
                    "pycodestyle": {"enabled": True},
                    "pyflakes": {"enabled": True},
                    "pylint": {"enabled": False},
                    "rope_completion": {"enabled": True},
                    "rope_rename": {"enabled": True},
                }
            }
        },
    ),
    "python-pyright": LSPServerConfig(
        name="python-pyright",
        command=["pyright-langserver", "--stdio"],
        file_patterns=["*.py"],
        language_id="python",
        settings={
            "python": {
                "analysis": {
                    "autoSearchPaths": True,
                    "diagnosticMode": "workspace",
                    "useLibraryCodeForTypes": True,
                }
            }
        },
    ),
    "typescript": LSPServerConfig(
        name="typescript",
        command=["typescript-language-server", "--stdio"],
        file_patterns=["*.ts", "*.tsx", "*.js", "*.jsx"],
        language_id="typescript",
        init_options={
            "preferences": {
                "includeInlayParameterNameHints": "all",
                "includeInlayVariableTypeHints": True,
            }
        },
    ),
    "rust": LSPServerConfig(
        name="rust",
        command=["rust-analyzer"],
        file_patterns=["*.rs"],
        language_id="rust",
        settings={
            "rust-analyzer": {
                "checkOnSave": {"command": "clippy"},
            }
        },
    ),
    "go": LSPServerConfig(
        name="go",
        command=["gopls"],
        file_patterns=["*.go"],
        language_id="go",
        settings={
            "gopls": {
                "staticcheck": True,
                "usePlaceholders": True,
            }
        },
    ),
    "c-cpp": LSPServerConfig(
        name="c-cpp",
        command=["clangd"],
        file_patterns=["*.c", "*.cpp", "*.h", "*.hpp", "*.cc"],
        language_id="cpp",
    ),
    "json": LSPServerConfig(
        name="json",
        command=["vscode-json-language-server", "--stdio"],
        file_patterns=["*.json", "*.jsonc"],
        language_id="json",
    ),
    "yaml": LSPServerConfig(
        name="yaml",
        command=["yaml-language-server", "--stdio"],
        file_patterns=["*.yaml", "*.yml"],
        language_id="yaml",
    ),
    "html": LSPServerConfig(
        name="html",
        command=["vscode-html-language-server", "--stdio"],
        file_patterns=["*.html", "*.htm"],
        language_id="html",
    ),
    "css": LSPServerConfig(
        name="css",
        command=["vscode-css-language-server", "--stdio"],
        file_patterns=["*.css", "*.scss", "*.less"],
        language_id="css",
    ),
}


def get_server_config(name: str) -> LSPServerConfig | None:
    """
    Get a built-in server configuration by name.

    Args:
        name: Server name

    Returns:
        LSPServerConfig or None if not found
    """
    return BUILTIN_SERVERS.get(name)


def get_server_for_file(file_path: str) -> LSPServerConfig | None:
    """
    Get server configuration for a file based on its extension.

    Args:
        file_path: Path to the file

    Returns:
        LSPServerConfig or None if no matching server
    """
    import fnmatch
    from pathlib import Path

    file_name = Path(file_path).name

    for config in BUILTIN_SERVERS.values():
        if config.enabled:
            for pattern in config.file_patterns:
                if fnmatch.fnmatch(file_name, pattern):
                    return config

    return None


def list_builtin_servers() -> list[str]:
    """
    List names of all built-in servers.

    Returns:
        List of server names
    """
    return list(BUILTIN_SERVERS.keys())


def load_servers_from_config(config: dict) -> dict[str, LSPServerConfig]:
    """
    Load server configurations from brainchain config.

    Args:
        config: LSP section of brainchain config

    Returns:
        Dict of server name to LSPServerConfig
    """
    servers = {}

    for name, server_config in config.get("servers", {}).items():
        if isinstance(server_config, dict):
            # Custom server from config
            command = server_config.get("command", [])
            if isinstance(command, str):
                command = command.split()

            servers[name] = LSPServerConfig(
                name=name,
                command=command,
                file_patterns=server_config.get("file_patterns", []),
                language_id=server_config.get("language_id", ""),
                init_options=server_config.get("init_options", {}),
                settings=server_config.get("settings", {}),
                enabled=server_config.get("enabled", True),
                auto_start=server_config.get("auto_start", False),
            )
        elif name in BUILTIN_SERVERS:
            # Enable/configure built-in server
            builtin = BUILTIN_SERVERS[name]
            servers[name] = LSPServerConfig(
                name=name,
                command=builtin.command.copy(),
                file_patterns=builtin.file_patterns.copy(),
                language_id=builtin.language_id,
                init_options=builtin.init_options.copy(),
                settings=builtin.settings.copy(),
                enabled=True,
                auto_start=False,
            )

    return servers

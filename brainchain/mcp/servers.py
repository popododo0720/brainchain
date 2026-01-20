"""
Built-in MCP server configurations.

Provides pre-configured server settings for common MCP servers.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    command: list[str]
    name: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    env: dict[str, str] | None = None
    enabled: bool = True
    auto_connect: bool = False
    timeout: int = 30

    def with_args(self, **kwargs) -> "MCPServerConfig":
        """Create a copy with updated args."""
        new_args = {**self.args, **kwargs}
        return MCPServerConfig(
            command=self.command.copy(),
            name=self.name,
            args=new_args,
            env=self.env.copy() if self.env else None,
            enabled=self.enabled,
            auto_connect=self.auto_connect,
            timeout=self.timeout,
        )


# Built-in server configurations
BUILTIN_SERVERS: dict[str, MCPServerConfig] = {
    "filesystem": MCPServerConfig(
        name="filesystem",
        command=["npx", "-y", "@modelcontextprotocol/server-filesystem"],
        args={"allowed_paths": ["."]},
        enabled=True,
    ),
    "fetch": MCPServerConfig(
        name="fetch",
        command=["npx", "-y", "@modelcontextprotocol/server-fetch"],
        args={},
        enabled=False,
    ),
    "memory": MCPServerConfig(
        name="memory",
        command=["npx", "-y", "@modelcontextprotocol/server-memory"],
        args={},
        enabled=False,
    ),
    "puppeteer": MCPServerConfig(
        name="puppeteer",
        command=["npx", "-y", "@modelcontextprotocol/server-puppeteer"],
        args={},
        enabled=False,
    ),
    "brave-search": MCPServerConfig(
        name="brave-search",
        command=["npx", "-y", "@modelcontextprotocol/server-brave-search"],
        args={},
        env={"BRAVE_API_KEY": ""},
        enabled=False,
    ),
    "github": MCPServerConfig(
        name="github",
        command=["npx", "-y", "@modelcontextprotocol/server-github"],
        args={},
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": ""},
        enabled=False,
    ),
    "postgres": MCPServerConfig(
        name="postgres",
        command=["npx", "-y", "@modelcontextprotocol/server-postgres"],
        args={"connection_string": ""},
        enabled=False,
    ),
    "sqlite": MCPServerConfig(
        name="sqlite",
        command=["npx", "-y", "@modelcontextprotocol/server-sqlite"],
        args={"database_path": ""},
        enabled=False,
    ),
    "slack": MCPServerConfig(
        name="slack",
        command=["npx", "-y", "@modelcontextprotocol/server-slack"],
        args={},
        env={"SLACK_BOT_TOKEN": "", "SLACK_TEAM_ID": ""},
        enabled=False,
    ),
    "google-maps": MCPServerConfig(
        name="google-maps",
        command=["npx", "-y", "@modelcontextprotocol/server-google-maps"],
        args={},
        env={"GOOGLE_MAPS_API_KEY": ""},
        enabled=False,
    ),
}


def get_server_config(name: str) -> MCPServerConfig | None:
    """
    Get a built-in server configuration by name.

    Args:
        name: Server name

    Returns:
        MCPServerConfig or None if not found
    """
    return BUILTIN_SERVERS.get(name)


def list_builtin_servers() -> list[str]:
    """
    List names of all built-in servers.

    Returns:
        List of server names
    """
    return list(BUILTIN_SERVERS.keys())


def create_server_config(
    command: list[str],
    name: str = "custom",
    **kwargs,
) -> MCPServerConfig:
    """
    Create a custom server configuration.

    Args:
        command: Command to start the server
        name: Server name
        **kwargs: Additional configuration options

    Returns:
        MCPServerConfig instance
    """
    return MCPServerConfig(
        command=command,
        name=name,
        **kwargs,
    )


def load_servers_from_config(config: dict) -> dict[str, MCPServerConfig]:
    """
    Load server configurations from brainchain config.

    Args:
        config: MCP section of brainchain config

    Returns:
        Dict of server name to MCPServerConfig
    """
    servers = {}

    for name, server_config in config.get("servers", {}).items():
        if isinstance(server_config, dict):
            # Custom server from config
            command = server_config.get("command", [])
            if isinstance(command, str):
                command = command.split()

            servers[name] = MCPServerConfig(
                name=name,
                command=command,
                args=server_config.get("args", {}),
                env=server_config.get("env"),
                enabled=server_config.get("enabled", True),
                auto_connect=server_config.get("auto_connect", False),
                timeout=server_config.get("timeout", 30),
            )
        elif name in BUILTIN_SERVERS:
            # Enable/configure built-in server
            builtin = BUILTIN_SERVERS[name]
            servers[name] = MCPServerConfig(
                name=name,
                command=builtin.command.copy(),
                args=builtin.args.copy(),
                env=builtin.env.copy() if builtin.env else None,
                enabled=True,
                auto_connect=False,
                timeout=builtin.timeout,
            )

    return servers

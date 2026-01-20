"""
Custom command system.

Allows plugins to register /commands that users can invoke.

Example:
```python
from brainchain.plugins import command, CommandRegistry

@command("hello", description="Say hello")
def hello_command(args: str, ctx: CommandContext) -> str:
    return f"Hello, {args or 'World'}!"

# Or register manually:
registry = CommandRegistry()
registry.register("hello", hello_command, description="Say hello")
```
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING
import re

if TYPE_CHECKING:
    from ..executor import Executor


@dataclass
class CommandContext:
    """Context passed to command handlers."""

    cwd: str = ""
    session_id: str | None = None
    executor: "Executor | None" = None
    config: dict = field(default_factory=dict)

    # For passing data between commands
    data: dict = field(default_factory=dict)


@dataclass
class Command:
    """Represents a registered command."""

    name: str
    handler: Callable[[str, CommandContext], str | None]
    description: str = ""
    usage: str = ""
    aliases: list[str] = field(default_factory=list)
    hidden: bool = False

    # Plugin that registered this command
    plugin: str | None = None


# Decorator storage
_pending_commands: list[tuple[str, Callable, dict]] = []


def command(
    name: str,
    description: str = "",
    usage: str = "",
    aliases: list[str] | None = None,
    hidden: bool = False,
) -> Callable:
    """
    Decorator to register a command.

    Args:
        name: Command name (without /)
        description: Short description
        usage: Usage example
        aliases: Alternative names
        hidden: Hide from help listing

    Example:
        @command("greet", description="Greet someone", usage="/greet <name>")
        def greet(args: str, ctx: CommandContext) -> str:
            return f"Hello, {args}!"
    """
    def decorator(fn: Callable) -> Callable:
        _pending_commands.append((name, fn, {
            "description": description,
            "usage": usage,
            "aliases": aliases or [],
            "hidden": hidden,
        }))
        return fn
    return decorator


class CommandRegistry:
    """
    Registry for custom commands.

    Commands are invoked with /name <args>
    """

    def __init__(self):
        self._commands: dict[str, Command] = {}
        self._aliases: dict[str, str] = {}

        # Register built-in commands
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register built-in commands."""
        self.register("help", self._cmd_help, description="Show available commands")
        self.register("list", self._cmd_list, description="List agents and roles")
        self.register("status", self._cmd_status, description="Show current status")
        self.register("clear", self._cmd_clear, description="Clear screen")
        self.register("exit", self._cmd_exit, description="Exit brainchain", aliases=["quit", "q"])

    def register(
        self,
        name: str,
        handler: Callable[[str, CommandContext], str | None],
        description: str = "",
        usage: str = "",
        aliases: list[str] | None = None,
        hidden: bool = False,
        plugin: str | None = None,
    ) -> None:
        """
        Register a command.

        Args:
            name: Command name (without /)
            handler: Function to handle the command
            description: Short description
            usage: Usage example
            aliases: Alternative names
            hidden: Hide from help listing
            plugin: Plugin that registered this
        """
        cmd = Command(
            name=name,
            handler=handler,
            description=description,
            usage=usage or f"/{name}",
            aliases=aliases or [],
            hidden=hidden,
            plugin=plugin,
        )

        self._commands[name] = cmd

        for alias in cmd.aliases:
            self._aliases[alias] = name

    def unregister(self, name: str) -> bool:
        """
        Unregister a command.

        Args:
            name: Command name

        Returns:
            True if removed
        """
        if name not in self._commands:
            return False

        cmd = self._commands[name]

        # Remove aliases
        for alias in cmd.aliases:
            if alias in self._aliases:
                del self._aliases[alias]

        del self._commands[name]
        return True

    def get(self, name: str) -> Command | None:
        """Get a command by name or alias."""
        # Check direct name
        if name in self._commands:
            return self._commands[name]

        # Check alias
        if name in self._aliases:
            return self._commands[self._aliases[name]]

        return None

    def list_commands(self, include_hidden: bool = False) -> list[Command]:
        """List all registered commands."""
        commands = list(self._commands.values())
        if not include_hidden:
            commands = [c for c in commands if not c.hidden]
        return sorted(commands, key=lambda c: c.name)

    def parse_and_execute(
        self,
        input_text: str,
        ctx: CommandContext | None = None,
    ) -> tuple[bool, str | None]:
        """
        Parse input and execute if it's a command.

        Args:
            input_text: User input
            ctx: Command context

        Returns:
            Tuple of (is_command, result)
        """
        input_text = input_text.strip()

        if not input_text.startswith("/"):
            return False, None

        # Parse command and args
        match = re.match(r"^/(\w+)(?:\s+(.*))?$", input_text)
        if not match:
            return True, "Invalid command format. Use /help for available commands."

        cmd_name = match.group(1)
        args = match.group(2) or ""

        cmd = self.get(cmd_name)
        if not cmd:
            return True, f"Unknown command: /{cmd_name}. Use /help for available commands."

        ctx = ctx or CommandContext()

        try:
            result = cmd.handler(args, ctx)
            return True, result
        except Exception as e:
            return True, f"Command error: {e}"

    def load_pending(self, plugin_name: str | None = None) -> int:
        """
        Load commands registered via @command decorator.

        Args:
            plugin_name: Plugin name to tag commands with

        Returns:
            Number of commands loaded
        """
        global _pending_commands

        loaded = 0
        for name, handler, opts in _pending_commands:
            self.register(
                name=name,
                handler=handler,
                description=opts.get("description", ""),
                usage=opts.get("usage", ""),
                aliases=opts.get("aliases", []),
                hidden=opts.get("hidden", False),
                plugin=plugin_name,
            )
            loaded += 1

        _pending_commands = []
        return loaded

    # Built-in command handlers

    def _cmd_help(self, args: str, ctx: CommandContext) -> str:
        """Show help for commands."""
        if args:
            # Help for specific command
            cmd = self.get(args)
            if cmd:
                lines = [f"/{cmd.name} - {cmd.description}"]
                if cmd.usage:
                    lines.append(f"Usage: {cmd.usage}")
                if cmd.aliases:
                    lines.append(f"Aliases: {', '.join('/' + a for a in cmd.aliases)}")
                return "\n".join(lines)
            return f"Unknown command: /{args}"

        # List all commands
        commands = self.list_commands()
        lines = ["Available commands:", ""]

        max_name_len = max(len(c.name) for c in commands) if commands else 10

        for cmd in commands:
            padding = " " * (max_name_len - len(cmd.name) + 2)
            lines.append(f"  /{cmd.name}{padding}{cmd.description}")

        lines.append("")
        lines.append("Use /help <command> for more info")

        return "\n".join(lines)

    def _cmd_list(self, args: str, ctx: CommandContext) -> str:
        """List agents and roles."""
        config = ctx.config
        lines = []

        if "agents" in config:
            lines.append("Agents:")
            for name in config["agents"]:
                lines.append(f"  - {name}")

        if "roles" in config:
            lines.append("\nRoles:")
            for name, cfg in config["roles"].items():
                agent = cfg.get("agent", "?")
                lines.append(f"  - {name} -> {agent}")

        return "\n".join(lines) if lines else "No agents or roles configured."

    def _cmd_status(self, args: str, ctx: CommandContext) -> str:
        """Show current status."""
        lines = [
            "Brainchain Status",
            f"  CWD: {ctx.cwd}",
            f"  Session: {ctx.session_id or 'None'}",
        ]
        return "\n".join(lines)

    def _cmd_clear(self, args: str, ctx: CommandContext) -> str:
        """Clear screen."""
        return "\033[2J\033[H"  # ANSI escape codes

    def _cmd_exit(self, args: str, ctx: CommandContext) -> str:
        """Exit command."""
        raise SystemExit(0)

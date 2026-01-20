"""
Custom commands for hello_plugin.
"""

from brainchain.plugins.commands import CommandContext


def register_commands(registry):
    """Register plugin commands."""

    # /hello command
    registry.register(
        name="hello",
        handler=cmd_hello,
        description="Say hello to someone",
        usage="/hello <name>",
        plugin="hello_plugin",
    )

    # /time command
    registry.register(
        name="time",
        handler=cmd_time,
        description="Show current time",
        usage="/time",
        plugin="hello_plugin",
    )

    # /cowsay command
    registry.register(
        name="cowsay",
        handler=cmd_cowsay,
        description="Make a cow say something",
        usage="/cowsay <message>",
        plugin="hello_plugin",
    )


def cmd_hello(args: str, ctx: CommandContext) -> str:
    """Say hello to someone."""
    name = args.strip() if args else "World"
    return f"Hello, {name}! Welcome to Brainchain!"


def cmd_time(args: str, ctx: CommandContext) -> str:
    """Show current time."""
    from datetime import datetime
    now = datetime.now()
    return f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}"


def cmd_cowsay(args: str, ctx: CommandContext) -> str:
    """Make a cow say something."""
    message = args.strip() if args else "Moo!"

    # Simple ASCII cow
    border = "-" * (len(message) + 2)
    cow = f"""
 {border}
< {message} >
 {border}
        \\   ^__^
         \\  (oo)\\_______
            (__)\\       )\\/\\
                ||----w |
                ||     ||
"""
    return cow

"""
Command palette widget for the Brainchain TUI.

Modal palette for executing commands (Ctrl+P).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

try:
    from textual.app import ComposeResult
    from textual.screen import ModalScreen
    from textual.containers import Container
    from textual.widgets import Static, Input, ListView, ListItem
    from textual.binding import Binding
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False


@dataclass
class Command:
    """A command definition."""
    id: str
    name: str
    shortcut: str | None = None
    icon: str = ""
    description: str = ""
    action: Callable[[], None] | None = None

    def format_display(self) -> str:
        """Format for display in palette."""
        shortcut_str = f"  {self.shortcut}" if self.shortcut else ""
        return f"{self.icon} {self.name:<30}{shortcut_str}"


# Default commands
DEFAULT_COMMANDS = [
    Command("new_session", "New Session", "Ctrl+N", "📁"),
    Command("session_palette", "Switch Session", "Ctrl+T", "🔄"),
    Command("toggle_sidebar", "Toggle Sidebar", "Ctrl+B", "📊"),
    Command("toggle_logs", "Toggle Logs", "Ctrl+L", "📋"),
    Command("change_theme", "Change Theme", None, "🎨"),
    Command("settings", "Settings", None, "⚙️"),
    Command("delete_session", "Delete Current Session", None, "🗑️"),
    Command("export_session", "Export Session", None, "📤"),
    Command("clear_logs", "Clear Logs", None, "🧹"),
    Command("refresh", "Refresh", "Ctrl+R", "🔃"),
    Command("help", "Help", "?", "❓"),
    Command("quit", "Quit", "Q", "🚪"),
]


if TEXTUAL_AVAILABLE:
    class CommandItem(ListItem):
        """A command item in the palette list."""

        def __init__(self, command: Command):
            """Initialize command item."""
            super().__init__()
            self.command = command

        def compose(self) -> ComposeResult:
            """Create the item content."""
            yield Static(self.command.format_display())


    class CommandPalette(ModalScreen):
        """
        Modal palette for command execution.

        Shows:
        - Search input
        - Command list with shortcuts
        - Fuzzy matching
        """

        DEFAULT_CSS = """
        CommandPalette {
            align: center middle;
        }

        CommandPalette > Container {
            width: 50;
            height: 18;
            border: solid $primary;
            background: $surface;
            padding: 1;
        }

        CommandPalette #command-input {
            margin-bottom: 1;
        }

        CommandPalette #command-list {
            height: 1fr;
        }

        CommandPalette ListItem {
            padding: 0 1;
        }

        CommandPalette ListItem:hover {
            background: $panel;
        }
        """

        BINDINGS = [
            Binding("escape", "close", "Close"),
            Binding("enter", "execute", "Execute"),
        ]

        def __init__(self, commands: list[Command] | None = None):
            """
            Initialize command palette.

            Args:
                commands: List of available commands
            """
            super().__init__()
            self._commands = commands or DEFAULT_COMMANDS.copy()
            self._filtered = self._commands.copy()

        def compose(self) -> ComposeResult:
            """Create the palette layout."""
            with Container():
                yield Input(
                    placeholder=">",
                    id="command-input",
                )
                yield ListView(id="command-list")

        def on_mount(self) -> None:
            """Initialize when mounted."""
            self._refresh_list()
            # Focus the input
            self.query_one("#command-input", Input).focus()

        def on_input_changed(self, event: Input.Changed) -> None:
            """Handle input changes."""
            if event.input.id == "command-input":
                self.filter_commands(event.value)

        def on_list_view_selected(self, event: ListView.Selected) -> None:
            """Handle command selection."""
            if event.item and isinstance(event.item, CommandItem):
                self.execute_command(event.item.command)

        def filter_commands(self, query: str) -> None:
            """Filter commands by search query."""
            query = query.lower().strip()

            if not query:
                self._filtered = self._commands.copy()
            else:
                self._filtered = [
                    cmd for cmd in self._commands
                    if self._fuzzy_match(cmd, query)
                ]

            self._refresh_list()

        def _fuzzy_match(self, command: Command, query: str) -> bool:
            """Check if command matches query (fuzzy)."""
            # Simple substring matching
            searchable = f"{command.name} {command.id} {command.description}".lower()
            return query in searchable

        def _refresh_list(self) -> None:
            """Refresh the command list."""
            try:
                list_view = self.query_one("#command-list", ListView)
                list_view.clear()

                for cmd in self._filtered:
                    list_view.append(CommandItem(cmd))
            except Exception:
                pass

        def execute_command(self, command: Command) -> None:
            """Execute a command and close palette."""
            self.app.pop_screen()

            # Execute the command's action or map to app action
            if command.action:
                command.action()
            else:
                # Try to call app action
                action_name = f"action_{command.id}"
                if hasattr(self.app, action_name):
                    getattr(self.app, action_name)()
                elif hasattr(self.app, command.id):
                    getattr(self.app, command.id)()

        def action_close(self) -> None:
            """Close the palette."""
            self.app.pop_screen()

        def action_execute(self) -> None:
            """Execute the highlighted command."""
            try:
                list_view = self.query_one("#command-list", ListView)
                if list_view.highlighted_child:
                    item = list_view.highlighted_child
                    if isinstance(item, CommandItem):
                        self.execute_command(item.command)
            except Exception:
                pass

        def add_command(self, command: Command) -> None:
            """Add a command to the palette."""
            self._commands.append(command)
            self._filtered = self._commands.copy()
            self._refresh_list()
else:
    class CommandPalette:
        """Stub when textual not available."""
        pass

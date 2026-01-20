"""
Keyboard bindings for the Brainchain TUI.

Defines global keyboard shortcuts and their handlers.
"""

from __future__ import annotations

try:
    from textual.binding import Binding
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    # Stub for when textual isn't available
    class Binding:
        def __init__(self, *args, **kwargs):
            pass


# Global keybindings
KEYBINDINGS = [
    Binding("ctrl+t", "show_session_palette", "Sessions", show=True),
    Binding("ctrl+n", "new_session", "New", show=True),
    Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=True),
    Binding("ctrl+p", "show_command_palette", "Commands", show=False),
    Binding("ctrl+l", "toggle_logs", "Logs", show=False),
    Binding("ctrl+r", "refresh", "Refresh", show=False),
    Binding("escape", "close_palette", "Close", show=False),
]


class KeybindingsMixin:
    """
    Mixin class that provides keybinding action handlers.

    Add this to your App class to get keyboard shortcut functionality.
    """

    def action_show_session_palette(self) -> None:
        """Show the session selection palette."""
        try:
            from .widgets.session_palette import SessionPalette
            self.push_screen(SessionPalette())
        except Exception:
            pass

    def action_new_session(self) -> None:
        """Create a new session."""
        # Notify the parent that a new session is requested
        if hasattr(self, 'create_new_session'):
            self.create_new_session()

    def action_toggle_sidebar(self) -> None:
        """Toggle the session sidebar visibility."""
        try:
            sidebar = self.query_one("#sidebar")
            sidebar.toggle_class("hidden")
        except Exception:
            pass

    def action_show_command_palette(self) -> None:
        """Show the command palette."""
        try:
            from .widgets.command_palette import CommandPalette
            self.push_screen(CommandPalette())
        except Exception:
            pass

    def action_toggle_logs(self) -> None:
        """Toggle the logs panel."""
        # Switch to logs tab
        if hasattr(self, 'action_show_tab'):
            self.action_show_tab('logs')

    def action_refresh(self) -> None:
        """Refresh the current view."""
        self.refresh()

    def action_close_palette(self) -> None:
        """Close any open palette/modal."""
        try:
            if hasattr(self, 'screen_stack') and len(self.screen_stack) > 1:
                self.pop_screen()
        except Exception:
            pass

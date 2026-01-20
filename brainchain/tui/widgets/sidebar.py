"""
Session sidebar widget for the Brainchain TUI.

Displays a list of sessions for quick navigation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.widgets import Static, ListView, ListItem, Button
    from textual.reactive import reactive
    from textual.message import Message
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

if TYPE_CHECKING:
    from ...session.models import Session


if TEXTUAL_AVAILABLE:
    class SessionListItem(ListItem):
        """A session item in the sidebar list."""

        def __init__(self, session: "Session", is_current: bool = False):
            """
            Initialize session list item.

            Args:
                session: Session data
                is_current: Whether this is the current session
            """
            super().__init__()
            self.session = session
            self.is_current = is_current

        def compose(self) -> ComposeResult:
            """Create the item content."""
            # Get display name
            name = getattr(self.session, 'display_name', None)
            if not name:
                name = getattr(self.session, 'name', None) or self.session.id[:8]

            # Status indicator
            indicator = "● " if self.is_current else "○ "

            yield Static(f"{indicator}{name}")


    class SessionSidebar(Container):
        """
        Sidebar showing session list.

        Features:
        - Session list with names
        - Current session highlight
        - Click to switch sessions
        - New session button
        """

        DEFAULT_CSS = """
        SessionSidebar {
            width: 20;
            background: $surface;
            border-right: solid $border;
            padding: 1;
        }

        SessionSidebar .sidebar-title {
            text-style: bold;
            color: $primary;
            margin-bottom: 1;
        }

        SessionSidebar #session-list {
            height: 1fr;
        }

        SessionSidebar #new-session {
            margin-top: 1;
            width: 100%;
        }

        SessionSidebar ListView > ListItem {
            padding: 0 1;
        }

        SessionSidebar ListView > ListItem:hover {
            background: $panel;
        }

        SessionSidebar .current-session {
            background: $panel;
            text-style: bold;
        }
        """

        class SessionSelected(Message):
            """Message when a session is selected."""

            def __init__(self, session_id: str) -> None:
                super().__init__()
                self.session_id = session_id

        class NewSessionRequested(Message):
            """Message when new session is requested."""
            pass

        def __init__(self, **kwargs):
            """Initialize sidebar."""
            super().__init__(**kwargs)
            self._sessions: list["Session"] = []
            self._current_session: "Session | None" = None

        def compose(self) -> ComposeResult:
            """Create the sidebar layout."""
            yield Static("Sessions", classes="sidebar-title")
            yield ListView(id="session-list")
            yield Button("[+] New", id="new-session", variant="primary")

        def on_mount(self) -> None:
            """Load sessions when mounted."""
            self.load_sessions()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            """Handle new session button."""
            if event.button.id == "new-session":
                self.post_message(self.NewSessionRequested())

        def on_list_view_selected(self, event: ListView.Selected) -> None:
            """Handle session selection."""
            if event.item and isinstance(event.item, SessionListItem):
                session_id = event.item.session.id
                self.post_message(self.SessionSelected(session_id))

        def load_sessions(self) -> None:
            """Load sessions from database."""
            try:
                from ...session.manager import SessionManager

                manager = SessionManager()
                self._sessions = manager.list_sessions(limit=20)
                self._refresh_list()
            except Exception:
                # Silently fail - sessions may not be available
                pass

        def set_sessions(self, sessions: list["Session"]) -> None:
            """Set the session list directly."""
            self._sessions = sessions
            self._refresh_list()

        def set_current_session(self, session: "Session | None") -> None:
            """Set the current session."""
            self._current_session = session
            self._refresh_list()

        def _refresh_list(self) -> None:
            """Refresh the session list."""
            try:
                list_view = self.query_one("#session-list", ListView)
                list_view.clear()

                for session in self._sessions:
                    is_current = (
                        self._current_session is not None and
                        session.id == self._current_session.id
                    )
                    item = SessionListItem(session, is_current=is_current)
                    if is_current:
                        item.add_class("current-session")
                    list_view.append(item)
            except Exception:
                pass

        def add_session(self, session: "Session") -> None:
            """Add a session to the top of the list."""
            self._sessions.insert(0, session)
            self._refresh_list()
else:
    class SessionSidebar:
        """Stub when textual not available."""
        pass

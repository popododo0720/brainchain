"""
Session palette widget for the Brainchain TUI.

Modal palette for quick session switching (Ctrl+T).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

try:
    from textual.app import ComposeResult
    from textual.screen import ModalScreen
    from textual.containers import Container, Vertical
    from textual.widgets import Static, Input, ListView, ListItem
    from textual.binding import Binding
    from textual.message import Message
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

if TYPE_CHECKING:
    from ...session.models import Session


if TEXTUAL_AVAILABLE:
    class SessionItem(ListItem):
        """A session item in the palette list."""

        def __init__(self, session: "Session"):
            """Initialize session item."""
            super().__init__()
            self.session = session

        def compose(self) -> ComposeResult:
            """Create the item content."""
            # Get display name
            name = getattr(self.session, 'display_name', None)
            if not name:
                name = getattr(self.session, 'name', None) or self.session.id[:8]

            # Format date
            created = self.session.created_at
            now = datetime.now()

            if created.date() == now.date():
                date_str = f"today {created.strftime('%H:%M')}"
            elif (now - created).days == 1:
                date_str = "yesterday"
            else:
                date_str = created.strftime("%Y-%m-%d")

            # Status icon
            status_icons = {
                "active": "●",
                "completed": "✓",
                "failed": "✗",
                "interrupted": "◐",
            }
            status = self.session.status.value
            icon = status_icons.get(status, "○")

            yield Static(f"{icon} {name:<20} {date_str:>15}")


    class SessionPalette(ModalScreen):
        """
        Modal palette for session selection.

        Shows:
        - Search input
        - Session list
        - Keyboard navigation
        """

        DEFAULT_CSS = """
        SessionPalette {
            align: center middle;
        }

        SessionPalette > Container {
            width: 60;
            height: 20;
            border: solid $primary;
            background: $surface;
            padding: 1;
        }

        SessionPalette #search {
            margin-bottom: 1;
        }

        SessionPalette #session-list {
            height: 1fr;
        }

        SessionPalette .help-text {
            color: $text-muted;
            text-align: center;
            margin-top: 1;
        }

        SessionPalette ListItem {
            padding: 0 1;
        }

        SessionPalette ListItem:hover {
            background: $panel;
        }
        """

        BINDINGS = [
            Binding("escape", "close", "Close"),
            Binding("enter", "select", "Select"),
            Binding("ctrl+n", "new_session", "New Session"),
        ]

        class SessionChosen(Message):
            """Message when a session is chosen."""

            def __init__(self, session_id: str) -> None:
                super().__init__()
                self.session_id = session_id

        def __init__(self):
            """Initialize palette."""
            super().__init__()
            self._sessions: list["Session"] = []
            self._filtered: list["Session"] = []

        def compose(self) -> ComposeResult:
            """Create the palette layout."""
            with Container():
                yield Input(
                    placeholder="🔍 Search sessions...",
                    id="search",
                )
                yield ListView(id="session-list")
                yield Static(
                    "[Enter] Switch  [Ctrl+N] New  [Esc] Close",
                    classes="help-text",
                )

        def on_mount(self) -> None:
            """Load sessions when mounted."""
            self.load_sessions()
            # Focus the search input
            self.query_one("#search", Input).focus()

        def on_input_changed(self, event: Input.Changed) -> None:
            """Handle search input changes."""
            if event.input.id == "search":
                self.filter_sessions(event.value)

        def on_list_view_selected(self, event: ListView.Selected) -> None:
            """Handle session selection."""
            if event.item and isinstance(event.item, SessionItem):
                self.select_session(event.item.session)

        def load_sessions(self) -> None:
            """Load sessions from database."""
            try:
                from ...session.manager import SessionManager

                manager = SessionManager()
                self._sessions = manager.list_sessions(limit=50)
                self._filtered = self._sessions.copy()
                self._refresh_list()
            except Exception:
                self._sessions = []
                self._filtered = []

        def filter_sessions(self, query: str) -> None:
            """Filter sessions by search query."""
            query = query.lower().strip()

            if not query:
                self._filtered = self._sessions.copy()
            else:
                self._filtered = [
                    s for s in self._sessions
                    if self._matches_query(s, query)
                ]

            self._refresh_list()

        def _matches_query(self, session: "Session", query: str) -> bool:
            """Check if session matches search query."""
            # Check name
            name = getattr(session, 'display_name', None)
            if not name:
                name = getattr(session, 'name', None) or session.id

            if query in name.lower():
                return True

            # Check prompt
            if query in session.initial_prompt.lower():
                return True

            # Check workflow
            if session.workflow_name and query in session.workflow_name.lower():
                return True

            return False

        def _refresh_list(self) -> None:
            """Refresh the session list."""
            try:
                list_view = self.query_one("#session-list", ListView)
                list_view.clear()

                for session in self._filtered:
                    list_view.append(SessionItem(session))
            except Exception:
                pass

        def select_session(self, session: "Session") -> None:
            """Select a session and close palette."""
            self.post_message(self.SessionChosen(session.id))
            self.app.pop_screen()

        def action_close(self) -> None:
            """Close the palette."""
            self.app.pop_screen()

        def action_select(self) -> None:
            """Select the highlighted session."""
            try:
                list_view = self.query_one("#session-list", ListView)
                if list_view.highlighted_child:
                    item = list_view.highlighted_child
                    if isinstance(item, SessionItem):
                        self.select_session(item.session)
            except Exception:
                pass

        def action_new_session(self) -> None:
            """Request a new session."""
            self.app.pop_screen()
            if hasattr(self.app, 'create_new_session'):
                self.app.create_new_session()
else:
    class SessionPalette:
        """Stub when textual not available."""
        pass

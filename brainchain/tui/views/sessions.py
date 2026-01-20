"""
Sessions view for the Brainchain TUI.

Displays session list with management capabilities.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

try:
    from textual.app import ComposeResult
    from textual.containers import Container, Horizontal
    from textual.widgets import Static, DataTable, Button
    from textual.reactive import reactive
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

if TYPE_CHECKING:
    from ...session.models import Session


if TEXTUAL_AVAILABLE:
    class SessionsView(Container):
        """
        View displaying session list and management.

        Shows:
        - List of all sessions
        - Session status and progress
        - Resume/Delete actions
        """

        DEFAULT_CSS = """
        SessionsView {
            padding: 1 2;
        }

        SessionsView .title {
            text-style: bold;
            color: $primary;
            margin-bottom: 1;
        }

        SessionsView #session-table {
            height: 1fr;
            border: solid $border;
        }

        SessionsView #actions {
            height: 3;
            margin-top: 1;
        }

        SessionsView Button {
            margin-right: 1;
        }
        """

        def __init__(self):
            """Initialize sessions view."""
            super().__init__()
            self._sessions: list["Session"] = []
            self._selected_id: str | None = None

        def compose(self) -> ComposeResult:
            """Create the view layout."""
            yield Static("## Sessions", classes="title")

            # Session table
            table = DataTable(id="session-table", cursor_type="row")
            table.add_columns("Name", "Status", "Workflow", "Created", "Tasks")
            yield table

            # Action buttons
            with Horizontal(id="actions"):
                yield Button("Resume", id="resume", variant="primary")
                yield Button("Delete", id="delete", variant="error")
                yield Button("Refresh", id="refresh", variant="default")

        def on_mount(self) -> None:
            """Load sessions when mounted."""
            self.load_sessions()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            """Handle button presses."""
            if event.button.id == "resume":
                self.resume_selected()
            elif event.button.id == "delete":
                self.delete_selected()
            elif event.button.id == "refresh":
                self.load_sessions()

        def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            """Handle row selection."""
            if event.row_key:
                self._selected_id = str(event.row_key.value)

        def load_sessions(self) -> None:
            """Load sessions from database."""
            try:
                from ...session.manager import SessionManager

                manager = SessionManager()
                self._sessions = manager.list_sessions(limit=50)
                self._refresh_table()
            except Exception as e:
                self.notify(f"Failed to load sessions: {e}", severity="error")

        def _refresh_table(self) -> None:
            """Refresh the session table."""
            try:
                table = self.query_one("#session-table", DataTable)
                table.clear()

                for session in self._sessions:
                    # Get display name
                    name = getattr(session, 'display_name', None)
                    if not name:
                        name = getattr(session, 'name', None) or session.id[:8]

                    # Status with icon
                    status_icons = {
                        "active": "🔄",
                        "completed": "✅",
                        "failed": "❌",
                        "interrupted": "⏸️",
                    }
                    status = session.status.value
                    icon = status_icons.get(status, "❓")

                    # Format date
                    created = session.created_at.strftime("%Y-%m-%d %H:%M")

                    # Workflow name
                    workflow = session.workflow_name or "default"

                    # Tasks (placeholder - would need to query)
                    tasks = "-"

                    table.add_row(
                        name,
                        f"{icon} {status}",
                        workflow,
                        created,
                        tasks,
                        key=session.id,
                    )
            except Exception:
                pass

        def resume_selected(self) -> None:
            """Resume the selected session."""
            if not self._selected_id:
                self.notify("No session selected", severity="warning")
                return

            try:
                # Find the session
                session = next(
                    (s for s in self._sessions if s.id == self._selected_id),
                    None
                )
                if session:
                    self.notify(f"Resuming session: {self._selected_id[:8]}...")
                    # This would trigger session resume in the main app
                    if hasattr(self.app, 'resume_session'):
                        self.app.resume_session(self._selected_id)
            except Exception as e:
                self.notify(f"Failed to resume: {e}", severity="error")

        def delete_selected(self) -> None:
            """Delete the selected session."""
            if not self._selected_id:
                self.notify("No session selected", severity="warning")
                return

            try:
                from ...session.manager import SessionManager

                manager = SessionManager()
                manager.delete_session(self._selected_id)
                self.notify(f"Deleted session: {self._selected_id[:8]}")
                self.load_sessions()
            except Exception as e:
                self.notify(f"Failed to delete: {e}", severity="error")

        def add_session(self, session: "Session") -> None:
            """Add a session to the list."""
            self._sessions.insert(0, session)
            self._refresh_table()
else:
    class SessionsView:
        """Stub when textual not available."""
        pass

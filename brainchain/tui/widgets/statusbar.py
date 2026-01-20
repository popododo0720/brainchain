"""
Status bar widget for the Brainchain TUI.

Displays current session status, progress, and context usage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    from textual.app import ComposeResult
    from textual.containers import Horizontal
    from textual.widgets import Static
    from textual.reactive import reactive
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

if TYPE_CHECKING:
    from ...session.models import Session


if TEXTUAL_AVAILABLE:
    class StatusBar(Static):
        """
        Status bar showing current session state.

        Displays:
        - Current role/status
        - Context usage percentage
        - Elapsed time
        - Session ID
        """

        DEFAULT_CSS = """
        StatusBar {
            background: $panel;
            color: $text;
            padding: 0 1;
            height: 1;
        }

        StatusBar .status-item {
            margin-right: 2;
        }

        StatusBar .separator {
            color: $text-muted;
        }
        """

        # Reactive properties
        session_name: reactive[str] = reactive("")
        tasks_done: reactive[int] = reactive(0)
        tasks_total: reactive[int] = reactive(0)
        context_percent: reactive[float] = reactive(0.0)
        elapsed_time: reactive[str] = reactive("")
        current_role: reactive[str] = reactive("")

        def __init__(self, **kwargs):
            """Initialize status bar."""
            super().__init__(**kwargs)
            self._session: "Session | None" = None

        def render(self) -> str:
            """Render the status bar content."""
            parts = []

            # Session name
            if self.session_name:
                parts.append(f"📁 {self.session_name}")

            # Current role
            if self.current_role:
                parts.append(f"● {self.current_role}")

            # Progress
            if self.tasks_total > 0:
                bar = self._progress_bar(self.tasks_done, self.tasks_total, width=8)
                parts.append(f"{bar} {self.tasks_done}/{self.tasks_total}")

            # Context usage
            if self.context_percent > 0:
                bar = self._progress_bar(self.context_percent, 100, width=6)
                parts.append(f"🧠 {bar} {self.context_percent:.0f}%")

            # Elapsed time
            if self.elapsed_time:
                parts.append(f"⏱ {self.elapsed_time}")

            return " │ ".join(parts) if parts else "Ready"

        def update_status(
            self,
            session: "Session | None" = None,
            tasks_done: int | None = None,
            tasks_total: int | None = None,
            context_percent: float | None = None,
            elapsed_time: str | None = None,
            current_role: str | None = None,
        ) -> None:
            """
            Update the status bar.

            Args:
                session: Current session
                tasks_done: Completed task count
                tasks_total: Total task count
                context_percent: Context usage percentage
                elapsed_time: Elapsed time string
                current_role: Current active role
            """
            if session is not None:
                self._session = session
                name = getattr(session, 'display_name', None)
                if not name:
                    name = getattr(session, 'name', None) or session.id[:8]
                self.session_name = name

            if tasks_done is not None:
                self.tasks_done = tasks_done

            if tasks_total is not None:
                self.tasks_total = tasks_total

            if context_percent is not None:
                self.context_percent = context_percent

            if elapsed_time is not None:
                self.elapsed_time = elapsed_time

            if current_role is not None:
                self.current_role = current_role

            self.refresh()

        def _progress_bar(
            self,
            current: float,
            total: float,
            width: int = 10,
        ) -> str:
            """Create a text progress bar."""
            if total == 0:
                return "░" * width

            ratio = min(current / total, 1.0)
            filled = int(width * ratio)
            empty = width - filled

            return "█" * filled + "░" * empty

        def set_role(self, role: str) -> None:
            """Set the current active role."""
            self.current_role = role
            self.refresh()

        def clear(self) -> None:
            """Clear all status."""
            self.session_name = ""
            self.tasks_done = 0
            self.tasks_total = 0
            self.context_percent = 0.0
            self.elapsed_time = ""
            self.current_role = ""
            self._session = None
            self.refresh()
else:
    class StatusBar:
        """Stub when textual not available."""
        pass

"""
Logs view for the Brainchain TUI.

Displays real-time logs from all agents.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

try:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.widgets import Static, Input, RichLog
    from textual.reactive import reactive
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False


@dataclass
class LogMessage:
    """A log message entry."""
    timestamp: datetime
    level: str  # debug, info, warning, error
    role: str   # planner, implementer, reviewer, etc.
    message: str

    def format(self, colors: bool = True) -> str:
        """Format the log message."""
        time_str = self.timestamp.strftime("%H:%M:%S")

        if colors:
            level_colors = {
                "debug": "[dim]",
                "info": "[cyan]",
                "warning": "[yellow]",
                "error": "[red]",
            }
            role_colors = {
                "planner": "[magenta]",
                "implementer": "[green]",
                "reviewer": "[blue]",
                "fixer": "[yellow]",
                "validator": "[cyan]",
            }

            level_color = level_colors.get(self.level, "")
            role_color = role_colors.get(self.role, "")

            return (
                f"[dim]{time_str}[/dim] "
                f"{level_color}[{self.level.upper():5}][/] "
                f"{role_color}[{self.role}][/] "
                f"{self.message}"
            )

        return f"{time_str} [{self.level.upper():5}] [{self.role}] {self.message}"


if TEXTUAL_AVAILABLE:
    class LogsView(Container):
        """
        View displaying real-time logs.

        Shows:
        - Log entries from all agents
        - Filter by role or level
        - Real-time streaming
        """

        DEFAULT_CSS = """
        LogsView {
            padding: 1 2;
        }

        LogsView .title {
            text-style: bold;
            color: $primary;
            margin-bottom: 1;
        }

        LogsView #log-filter {
            height: 3;
            margin-bottom: 1;
        }

        LogsView #log-view {
            height: 1fr;
            border: solid $border;
            padding: 1;
        }
        """

        filter_text: reactive[str] = reactive("")

        def __init__(self):
            """Initialize logs view."""
            super().__init__()
            self._logs: list[LogMessage] = []
            self._filter: str = ""

        def compose(self) -> ComposeResult:
            """Create the view layout."""
            yield Static("## Logs", classes="title")
            yield Input(
                placeholder="Filter logs (e.g., 'planner', 'error')...",
                id="log-filter",
            )
            yield RichLog(id="log-view", highlight=True, markup=True)

        def on_input_changed(self, event: Input.Changed) -> None:
            """Handle filter input changes."""
            if event.input.id == "log-filter":
                self._filter = event.value.lower()
                self._refresh_logs()

        def add_log(
            self,
            message: str,
            level: str = "info",
            role: str = "system",
        ) -> None:
            """
            Add a log message.

            Args:
                message: Log message text
                level: Log level (debug, info, warning, error)
                role: Role that generated the log
            """
            log = LogMessage(
                timestamp=datetime.now(),
                level=level,
                role=role,
                message=message,
            )
            self._logs.append(log)

            # Add to view if matches filter
            if self._matches_filter(log):
                try:
                    log_view = self.query_one("#log-view", RichLog)
                    log_view.write(log.format(colors=True))
                except Exception:
                    pass

        def _matches_filter(self, log: LogMessage) -> bool:
            """Check if log matches current filter."""
            if not self._filter:
                return True

            filter_lower = self._filter.lower()
            return (
                filter_lower in log.level.lower() or
                filter_lower in log.role.lower() or
                filter_lower in log.message.lower()
            )

        def _refresh_logs(self) -> None:
            """Refresh log display with current filter."""
            try:
                log_view = self.query_one("#log-view", RichLog)
                log_view.clear()

                for log in self._logs:
                    if self._matches_filter(log):
                        log_view.write(log.format(colors=True))
            except Exception:
                pass

        def clear(self) -> None:
            """Clear all logs."""
            self._logs.clear()
            try:
                self.query_one("#log-view", RichLog).clear()
            except Exception:
                pass

        def export_logs(self, path: str) -> None:
            """Export logs to a file."""
            with open(path, "w") as f:
                for log in self._logs:
                    f.write(log.format(colors=False) + "\n")
else:
    class LogsView:
        """Stub when textual not available."""
        pass

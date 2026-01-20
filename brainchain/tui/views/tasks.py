"""
Tasks view for the Brainchain TUI.

Displays real-time task execution progress.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

try:
    from textual.app import ComposeResult
    from textual.containers import Container, VerticalScroll
    from textual.widgets import Static, DataTable, ProgressBar, RichLog
    from textual.reactive import reactive
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False


@dataclass
class TaskInfo:
    """Information about a task."""
    id: str
    role: str
    status: str = "pending"
    progress: float = 0.0
    start_time: float | None = None
    end_time: float | None = None
    output: str = ""
    error: str | None = None

    @property
    def duration(self) -> str:
        """Get formatted duration."""
        if self.start_time is None:
            return "--:--"
        end = self.end_time or time.time()
        seconds = int(end - self.start_time)
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"

    @property
    def status_icon(self) -> str:
        """Get status icon."""
        icons = {
            "pending": "⏳",
            "running": "🔄",
            "completed": "✅",
            "failed": "❌",
            "skipped": "⏭️",
        }
        return icons.get(self.status, "❓")


if TEXTUAL_AVAILABLE:
    class TasksView(Container):
        """
        View displaying task execution progress.

        Shows:
        - Task table with status
        - Progress bar
        - Current task output
        """

        DEFAULT_CSS = """
        TasksView {
            padding: 1 2;
        }

        TasksView .title {
            text-style: bold;
            color: $primary;
            margin-bottom: 1;
        }

        TasksView #task-table {
            height: 40%;
            border: solid $border;
        }

        TasksView #overall-progress {
            height: 1;
            margin: 1 0;
        }

        TasksView #current-output {
            height: 1fr;
            border: solid $border;
            padding: 1;
        }
        """

        tasks: reactive[list[TaskInfo]] = reactive(list, init=False)

        def __init__(self):
            """Initialize tasks view."""
            super().__init__()
            self._tasks: dict[str, TaskInfo] = {}
            self._current_task_id: str | None = None

        def compose(self) -> ComposeResult:
            """Create the view layout."""
            yield Static("## Task Progress", classes="title")

            # Task table
            table = DataTable(id="task-table")
            table.add_columns("ID", "Role", "Status", "Progress", "Duration")
            yield table

            # Overall progress
            yield ProgressBar(id="overall-progress", total=100, show_eta=False)

            # Current output
            yield Static("Current Output:", classes="subtitle")
            yield RichLog(id="current-output", highlight=True, markup=True)

        def on_mount(self) -> None:
            """Initialize when mounted."""
            pass

        def add_task(self, task_id: str, role: str) -> None:
            """Add a new task to tracking."""
            self._tasks[task_id] = TaskInfo(id=task_id, role=role)
            self._refresh_table()

        def update_task(
            self,
            task_id: str,
            status: str | None = None,
            progress: float | None = None,
            output: str | None = None,
            error: str | None = None,
        ) -> None:
            """Update task status."""
            if task_id not in self._tasks:
                return

            task = self._tasks[task_id]

            if status is not None:
                task.status = status
                if status == "running" and task.start_time is None:
                    task.start_time = time.time()
                    self._current_task_id = task_id
                elif status in ("completed", "failed"):
                    task.end_time = time.time()

            if progress is not None:
                task.progress = progress

            if output is not None:
                task.output = output
                self._update_output(output)

            if error is not None:
                task.error = error

            self._refresh_table()
            self._update_progress()

        def _refresh_table(self) -> None:
            """Refresh the task table."""
            try:
                table = self.query_one("#task-table", DataTable)
                table.clear()

                for task in self._tasks.values():
                    progress_bar = self._make_progress_bar(task.progress)
                    table.add_row(
                        task.id,
                        task.role,
                        f"{task.status_icon} {task.status}",
                        progress_bar,
                        task.duration,
                    )
            except Exception:
                pass

        def _update_progress(self) -> None:
            """Update overall progress bar."""
            try:
                progress_bar = self.query_one("#overall-progress", ProgressBar)
                if self._tasks:
                    completed = sum(
                        1 for t in self._tasks.values()
                        if t.status in ("completed", "skipped")
                    )
                    total = len(self._tasks)
                    progress_bar.update(progress=int(completed / total * 100))
            except Exception:
                pass

        def _update_output(self, output: str) -> None:
            """Update current output display."""
            try:
                log = self.query_one("#current-output", RichLog)
                log.write(output)
            except Exception:
                pass

        def _make_progress_bar(self, progress: float, width: int = 8) -> str:
            """Create a text progress bar."""
            filled = int(width * progress)
            empty = width - filled
            return "█" * filled + "░" * empty

        def clear_tasks(self) -> None:
            """Clear all tasks."""
            self._tasks.clear()
            self._current_task_id = None
            self._refresh_table()
            try:
                self.query_one("#overall-progress", ProgressBar).update(progress=0)
                self.query_one("#current-output", RichLog).clear()
            except Exception:
                pass
else:
    class TasksView:
        """Stub when textual not available."""
        pass

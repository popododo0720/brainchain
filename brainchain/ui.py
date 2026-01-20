"""
Progress display and UI utilities for Brainchain.

Provides:
- ANSI color support with graceful fallback
- Progress indicators for tasks and workflows
- Real-time parallel task status
- Summary reports
"""

import sys
import time
from dataclasses import dataclass, field
from typing import TextIO

from .compat import supports_color, supports_unicode

__all__ = [
    "ProgressUI",
    "Colors",
    "Symbols",
    "TaskStatus",
]


@dataclass
class Colors:
    """ANSI color codes with graceful fallback."""

    # Foreground colors
    RED: str = "\033[31m"
    GREEN: str = "\033[32m"
    YELLOW: str = "\033[33m"
    BLUE: str = "\033[34m"
    MAGENTA: str = "\033[35m"
    CYAN: str = "\033[36m"
    WHITE: str = "\033[37m"
    GRAY: str = "\033[90m"

    # Styles
    BOLD: str = "\033[1m"
    DIM: str = "\033[2m"
    RESET: str = "\033[0m"

    # Semantic colors
    SUCCESS: str = "\033[32m"  # Green
    ERROR: str = "\033[31m"    # Red
    WARNING: str = "\033[33m"  # Yellow
    INFO: str = "\033[36m"     # Cyan
    MUTED: str = "\033[90m"    # Gray

    @classmethod
    def disabled(cls) -> "Colors":
        """Return Colors instance with all codes empty (no colors)."""
        return cls(
            RED="", GREEN="", YELLOW="", BLUE="", MAGENTA="",
            CYAN="", WHITE="", GRAY="", BOLD="", DIM="", RESET="",
            SUCCESS="", ERROR="", WARNING="", INFO="", MUTED=""
        )


@dataclass
class Symbols:
    """Unicode/ASCII symbols for progress indicators."""

    CHECK: str = "✓"
    CROSS: str = "✗"
    SPINNER: str = "⏳"
    ARROW: str = "→"
    BULLET: str = "•"
    BOX_H: str = "━"
    TREE_BRANCH: str = "├─"
    TREE_END: str = "└─"

    @classmethod
    def ascii(cls) -> "Symbols":
        """Return ASCII-only symbols for limited terminals."""
        return cls(
            CHECK="[OK]",
            CROSS="[X]",
            SPINNER="...",
            ARROW="->",
            BULLET="*",
            BOX_H="-",
            TREE_BRANCH="|--",
            TREE_END="`--"
        )


@dataclass
class TaskStatus:
    """Status of a single task."""

    task_id: str
    role: str
    status: str = "pending"  # pending, running, completed, failed, skipped
    start_time: float | None = None
    end_time: float | None = None
    error: str | None = None
    output: str | None = None

    @property
    def duration(self) -> float | None:
        """Calculate task duration in seconds."""
        if self.start_time is None:
            return None
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def duration_str(self) -> str:
        """Format duration as human-readable string."""
        d = self.duration
        if d is None:
            return ""
        if d < 60:
            return f"{d:.1f}s"
        minutes = int(d // 60)
        seconds = d % 60
        return f"{minutes}m{seconds:.0f}s"


class ProgressUI:
    """
    Progress display for tasks and workflows.

    Handles real-time updates with proper terminal handling.
    """

    def __init__(
        self,
        verbose: bool = False,
        no_color: bool = False,
        stream: TextIO | None = None,
    ):
        """
        Initialize progress UI.

        Args:
            verbose: Show detailed output
            no_color: Disable colors even if terminal supports them
            stream: Output stream (defaults to stderr)
        """
        self.verbose = verbose
        self.stream = stream or sys.stderr

        # Determine color/unicode support
        use_color = supports_color() and not no_color
        use_unicode = supports_unicode()

        self.colors = Colors() if use_color else Colors.disabled()
        self.symbols = Symbols() if use_unicode else Symbols.ascii()

        # Track task states for real-time updates
        self.tasks: dict[str, TaskStatus] = {}
        self._start_time: float | None = None

    def _write(self, text: str, newline: bool = True) -> None:
        """Write to output stream."""
        self.stream.write(text)
        if newline:
            self.stream.write("\n")
        self.stream.flush()

    def _format_status_symbol(self, status: str) -> str:
        """Get colored symbol for task status."""
        c = self.colors
        s = self.symbols

        symbols = {
            "pending": f"{c.MUTED}{s.BULLET}{c.RESET}",
            "running": f"{c.YELLOW}{s.SPINNER}{c.RESET}",
            "completed": f"{c.GREEN}{s.CHECK}{c.RESET}",
            "failed": f"{c.RED}{s.CROSS}{c.RESET}",
            "skipped": f"{c.MUTED}skip{c.RESET}",
        }
        return symbols.get(status, s.BULLET)

    # === Task-level methods ===

    def task_started(self, task_id: str, role: str) -> None:
        """Called when a task begins execution."""
        self.tasks[task_id] = TaskStatus(
            task_id=task_id,
            role=role,
            status="running",
            start_time=time.time(),
        )
        if self.verbose:
            c = self.colors
            s = self.symbols
            self._write(f"  [{c.YELLOW}{s.SPINNER}{c.RESET}] {task_id} - {role} ...")

    def task_completed(
        self,
        task_id: str,
        success: bool,
        output: str | None = None,
        error: str | None = None,
    ) -> None:
        """Called when a task finishes."""
        task = self.tasks.get(task_id)
        if task:
            task.status = "completed" if success else "failed"
            task.end_time = time.time()
            task.output = output
            task.error = error

        c = self.colors
        s = self.symbols
        duration = task.duration_str if task else ""

        if success:
            symbol = f"{c.GREEN}{s.CHECK}{c.RESET}"
            suffix = f"{c.MUTED}({duration}){c.RESET}" if duration else ""
        else:
            symbol = f"{c.RED}{s.CROSS}{c.RESET}"
            err_msg = f": {error[:50]}..." if error and len(error) > 50 else (f": {error}" if error else "")
            suffix = f"{c.RED}{err_msg}{c.RESET}"

        role = task.role if task else "unknown"
        self._write(f"  [{symbol}] {task_id} - {role} {suffix}")

    def task_skipped(self, task_id: str, role: str, reason: str = "") -> None:
        """Called when a task is skipped."""
        self.tasks[task_id] = TaskStatus(
            task_id=task_id,
            role=role,
            status="skipped",
        )
        c = self.colors
        self._write(f"  [{c.MUTED}skip{c.RESET}] {task_id} - {role} {c.MUTED}({reason}){c.RESET}")

    # === Parallel execution methods ===

    def parallel_start(self, task_count: int) -> None:
        """Called when parallel execution begins."""
        self._start_time = time.time()
        c = self.colors
        self._write(f"\n{c.BOLD}Running {task_count} tasks...{c.RESET}")

    def parallel_summary(self, results: list[dict]) -> None:
        """Display summary after parallel execution."""
        c = self.colors
        s = self.symbols

        succeeded = sum(1 for r in results if r.get("success"))
        failed = len(results) - succeeded
        total_time = time.time() - (self._start_time or time.time())

        self._write(f"\n{s.BOX_H * 40}")

        if failed == 0:
            self._write(f"{c.GREEN}Results: {succeeded}/{len(results)} succeeded{c.RESET}")
        else:
            self._write(
                f"{c.YELLOW}Results: {c.GREEN}{succeeded} succeeded{c.RESET} | "
                f"{c.RED}{failed} failed{c.RESET}"
            )

        self._write(f"Total time: {total_time:.1f}s\n")

    # === Workflow methods ===

    def workflow_start(self, step_count: int) -> None:
        """Called when workflow execution begins."""
        self._start_time = time.time()
        c = self.colors
        s = self.symbols
        self._write(f"\n{c.BOLD}Workflow: {step_count} steps{c.RESET}")
        self._write(s.BOX_H * 40)

    def workflow_step_start(
        self,
        step_index: int,
        total_steps: int,
        role: str,
        is_parallel: bool = False,
        task_count: int = 1,
    ) -> None:
        """Called when a workflow step begins."""
        c = self.colors
        step_num = f"[{step_index + 1}/{total_steps}]"

        if is_parallel and task_count > 1:
            self._write(f"{step_num} {role} ({task_count} tasks)", newline=False)
        else:
            dots = "." * (25 - len(role))
            self._write(f"{step_num} {role} {dots} ", newline=False)

    def workflow_step_completed(
        self,
        success: bool,
        duration: float,
        message: str = "",
    ) -> None:
        """Called when a workflow step finishes."""
        c = self.colors
        s = self.symbols

        if success:
            self._write(f" {c.GREEN}{s.CHECK}{c.RESET} ({duration:.1f}s)")
        else:
            self._write(f" {c.RED}{s.CROSS}{c.RESET} ({message})")

    def workflow_step_tasks(self, task_results: list[dict]) -> None:
        """Display parallel task results within a workflow step."""
        c = self.colors
        s = self.symbols

        for i, result in enumerate(task_results):
            is_last = i == len(task_results) - 1
            branch = s.TREE_END if is_last else s.TREE_BRANCH
            task_id = result.get("id", f"task{i + 1}")
            success = result.get("success", False)

            symbol = f"{c.GREEN}{s.CHECK}{c.RESET}" if success else f"{c.RED}{s.CROSS}{c.RESET}"
            self._write(f"      {branch} [{symbol}] {task_id}")

    def workflow_step_skipped(
        self,
        step_index: int,
        total_steps: int,
        role: str,
    ) -> None:
        """Called when a workflow step is skipped."""
        c = self.colors
        step_num = f"[{step_index + 1}/{total_steps}]"
        self._write(f"{step_num} {c.MUTED}(skipped: {role}){c.RESET}")

    def workflow_summary(self, success: bool, steps_completed: int, total_steps: int) -> None:
        """Display summary after workflow execution."""
        c = self.colors
        s = self.symbols
        total_time = time.time() - (self._start_time or time.time())

        self._write(f"\n{s.BOX_H * 40}")
        if success:
            self._write(f"{c.GREEN}{c.BOLD}Workflow completed successfully!{c.RESET}")
        else:
            self._write(
                f"{c.RED}Workflow failed at step {steps_completed}/{total_steps}{c.RESET}"
            )
        self._write(f"Total time: {total_time:.1f}s\n")

    def workflow_jump(self, from_role: str, to_role: str, reason: str) -> None:
        """Called when workflow jumps to a different step."""
        c = self.colors
        s = self.symbols
        self._write(
            f"      {c.YELLOW}{s.ARROW} Jumping: {from_role} {s.ARROW} {to_role} ({reason}){c.RESET}"
        )

    # === Retry methods ===

    def retry_attempt(self, task_id: str, attempt: int, max_attempts: int, delay: int) -> None:
        """Called when retrying a failed task."""
        c = self.colors
        self._write(
            f"  {c.YELLOW}Retry {attempt}/{max_attempts} for {task_id} "
            f"(waiting {delay}s)...{c.RESET}"
        )

    # === General output ===

    def info(self, message: str) -> None:
        """Display info message."""
        c = self.colors
        self._write(f"{c.INFO}{message}{c.RESET}")

    def success(self, message: str) -> None:
        """Display success message."""
        c = self.colors
        s = self.symbols
        self._write(f"{c.GREEN}{s.CHECK} {message}{c.RESET}")

    def error(self, message: str) -> None:
        """Display error message."""
        c = self.colors
        s = self.symbols
        self._write(f"{c.RED}{s.CROSS} {message}{c.RESET}")

    def warning(self, message: str) -> None:
        """Display warning message."""
        c = self.colors
        self._write(f"{c.WARNING}Warning: {message}{c.RESET}")

    def debug(self, message: str) -> None:
        """Display debug message (only in verbose mode)."""
        if self.verbose:
            c = self.colors
            self._write(f"{c.MUTED}[debug] {message}{c.RESET}")

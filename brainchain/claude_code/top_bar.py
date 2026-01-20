"""
Top bar component for Claude Code integration.

Displays brainchain status at the top of Claude Code output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..session.models import Session


@dataclass
class TopBarConfig:
    """Configuration for the top bar."""

    show_session_name: bool = True
    show_progress: bool = True
    show_context: bool = True
    show_time: bool = True
    width: int = 60
    use_emoji: bool = True


class TopBar:
    """
    Renders a status bar for display above Claude Code output.

    Example output:
    ┌─ Brainchain ──────────────────────────────────────┐
    │ Session: Auth Feature │ Tasks: 3/5 │ Context: 62%   │
    └──────────────────────────────────────────────────────┘
    """

    def __init__(self, config: TopBarConfig | None = None):
        """
        Initialize top bar.

        Args:
            config: Display configuration
        """
        self.config = config or TopBarConfig()

    def render(
        self,
        session: "Session" | None = None,
        tasks_done: int = 0,
        tasks_total: int = 0,
        context_percent: float = 0.0,
        elapsed_time: str = "",
    ) -> str:
        """
        Render the top bar.

        Args:
            session: Current session
            tasks_done: Completed task count
            tasks_total: Total task count
            context_percent: Context usage percentage
            elapsed_time: Elapsed time string

        Returns:
            Rendered top bar string
        """
        width = self.config.width
        emoji = self.config.use_emoji

        # Build content parts
        parts = []

        # Session name
        if self.config.show_session_name and session:
            name = getattr(session, 'display_name', None)
            if not name:
                name = getattr(session, 'name', None) or session.id[:8]
            icon = "📁 " if emoji else ""
            parts.append(f"{icon}{name}")

        # Progress
        if self.config.show_progress and tasks_total > 0:
            bar = self._progress_bar(tasks_done, tasks_total, width=8)
            parts.append(f"{bar} {tasks_done}/{tasks_total}")

        # Context usage
        if self.config.show_context:
            icon = "🧠 " if emoji else "Ctx: "
            parts.append(f"{icon}{context_percent:.0f}%")

        # Time
        if self.config.show_time and elapsed_time:
            icon = "⏱ " if emoji else ""
            parts.append(f"{icon}{elapsed_time}")

        # Build the bar
        content = " │ ".join(parts)

        # Create box
        title = "🧠 Brainchain" if emoji else "Brainchain"

        # Calculate widths
        inner_width = max(len(content) + 2, width - 4)
        title_line = f"┌─ {title} " + "─" * (inner_width - len(title) - 3) + "┐"
        content_line = f"│ {content}" + " " * (inner_width - len(content) - 1) + "│"
        bottom_line = "└" + "─" * inner_width + "┘"

        return f"{title_line}\n{content_line}\n{bottom_line}"

    def render_minimal(
        self,
        session: "Session" | None = None,
        tasks_done: int = 0,
        tasks_total: int = 0,
    ) -> str:
        """
        Render a minimal one-line status.

        Args:
            session: Current session
            tasks_done: Completed task count
            tasks_total: Total task count

        Returns:
            Single-line status string
        """
        parts = []

        if session:
            name = getattr(session, 'display_name', None)
            if not name:
                name = getattr(session, 'name', None) or session.id[:8]
            parts.append(name)

        if tasks_total > 0:
            parts.append(f"{tasks_done}/{tasks_total}")

        return f"[{' | '.join(parts)}]" if parts else ""

    def inject_to_output(
        self,
        output: str,
        session: "Session" | None = None,
        **kwargs,
    ) -> str:
        """
        Inject top bar into Claude Code output.

        Args:
            output: Original Claude Code output
            session: Current session
            **kwargs: Additional render arguments

        Returns:
            Output with top bar prepended
        """
        top_bar = self.render(session=session, **kwargs)
        return f"{top_bar}\n\n{output}"

    def _progress_bar(
        self,
        current: int,
        total: int,
        width: int = 10,
    ) -> str:
        """Create a text progress bar."""
        if total == 0:
            return "░" * width

        filled = int(width * current / total)
        empty = width - filled

        return "█" * filled + "░" * empty

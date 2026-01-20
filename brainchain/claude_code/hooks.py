"""
Claude Code output hooks and integration.

Provides hooks to inject brainchain UI into Claude Code output.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Callable, Any

from .top_bar import TopBar, TopBarConfig

if TYPE_CHECKING:
    from ..session.models import Session


class UIMode(Enum):
    """UI display mode for Claude Code integration."""

    TOP_BAR = "top_bar"    # Full top bar
    MINIMAL = "minimal"    # Single line prefix
    SIDEBAR = "sidebar"    # TUI sidebar mode
    NONE = "none"          # No UI overlay


@dataclass
class HooksConfig:
    """Configuration for Claude Code hooks."""

    ui_mode: UIMode = UIMode.TOP_BAR
    show_progress: bool = True
    show_context: bool = True
    show_time: bool = True
    auto_inject: bool = True


class ClaudeCodeHooks:
    """
    Hooks for integrating brainchain UI with Claude Code.

    Provides output wrapping and event hooks for:
    - Displaying status before output
    - Updating progress during execution
    - Handling context changes
    """

    def __init__(self, config: HooksConfig | None = None):
        """
        Initialize Claude Code hooks.

        Args:
            config: Hooks configuration
        """
        self.config = config or HooksConfig()
        self.top_bar = TopBar(TopBarConfig(
            show_progress=self.config.show_progress,
            show_context=self.config.show_context,
            show_time=self.config.show_time,
        ))

        # State
        self._session: "Session" | None = None
        self._tasks_done: int = 0
        self._tasks_total: int = 0
        self._context_percent: float = 0.0
        self._elapsed_time: str = ""

        # Callbacks
        self._on_output: Callable[[str], str] | None = None

    def set_session(self, session: "Session") -> None:
        """Set the current session."""
        self._session = session

    def update_progress(
        self,
        done: int | None = None,
        total: int | None = None,
        context: float | None = None,
        elapsed: str | None = None,
    ) -> None:
        """
        Update progress state.

        Args:
            done: Tasks completed
            total: Total tasks
            context: Context usage percentage
            elapsed: Elapsed time string
        """
        if done is not None:
            self._tasks_done = done
        if total is not None:
            self._tasks_total = total
        if context is not None:
            self._context_percent = context
        if elapsed is not None:
            self._elapsed_time = elapsed

    def wrap_output(self, output: str) -> str:
        """
        Wrap Claude Code output with brainchain UI.

        Args:
            output: Original output

        Returns:
            Wrapped output based on UI mode
        """
        if self.config.ui_mode == UIMode.NONE:
            return output

        if self.config.ui_mode == UIMode.MINIMAL:
            prefix = self.top_bar.render_minimal(
                session=self._session,
                tasks_done=self._tasks_done,
                tasks_total=self._tasks_total,
            )
            return f"{prefix} {output}" if prefix else output

        if self.config.ui_mode == UIMode.TOP_BAR:
            return self.top_bar.inject_to_output(
                output,
                session=self._session,
                tasks_done=self._tasks_done,
                tasks_total=self._tasks_total,
                context_percent=self._context_percent,
                elapsed_time=self._elapsed_time,
            )

        # SIDEBAR mode is handled by TUI
        return output

    def before_output(self) -> str:
        """
        Get content to display before Claude output.

        Returns:
            Pre-output content
        """
        if self.config.ui_mode == UIMode.TOP_BAR:
            return self.top_bar.render(
                session=self._session,
                tasks_done=self._tasks_done,
                tasks_total=self._tasks_total,
                context_percent=self._context_percent,
                elapsed_time=self._elapsed_time,
            )
        return ""

    def after_command(self, result: Any) -> None:
        """
        Called after a command is executed.

        Args:
            result: Command result
        """
        # Update progress based on result
        if isinstance(result, dict):
            if "tasks_completed" in result:
                self._tasks_done = result["tasks_completed"]
            if "context_usage" in result:
                self._context_percent = result["context_usage"]

    def on_context_change(self, usage: float) -> None:
        """
        Called when context usage changes significantly.

        Args:
            usage: New context usage percentage
        """
        self._context_percent = usage * 100

    def register_output_hook(self, hook: Callable[[str], str]) -> None:
        """
        Register a custom output processing hook.

        Args:
            hook: Function that takes output and returns modified output
        """
        self._on_output = hook

    def get_status_line(self) -> str:
        """
        Get a single-line status for display.

        Returns:
            Status line string
        """
        parts = []

        if self._session:
            name = getattr(self._session, 'display_name', None)
            if not name:
                name = getattr(self._session, 'name', None) or self._session.id[:8]
            parts.append(f"📁 {name}")

        if self._tasks_total > 0:
            parts.append(f"📊 {self._tasks_done}/{self._tasks_total}")

        if self._context_percent > 0:
            parts.append(f"🧠 {self._context_percent:.0f}%")

        if self._elapsed_time:
            parts.append(f"⏱ {self._elapsed_time}")

        return " │ ".join(parts)


def create_hooks_from_config(config: dict[str, Any]) -> ClaudeCodeHooks:
    """
    Create ClaudeCodeHooks from config dictionary.

    Args:
        config: Configuration dict (from config.toml [claude_code] section)

    Returns:
        Configured ClaudeCodeHooks instance
    """
    mode_str = config.get("ui_mode", "top_bar")
    try:
        mode = UIMode(mode_str)
    except ValueError:
        mode = UIMode.TOP_BAR

    hooks_config = HooksConfig(
        ui_mode=mode,
        show_progress=config.get("show_progress", True),
        show_context=config.get("show_context", True),
        show_time=config.get("show_time", True),
        auto_inject=config.get("auto_inject", True),
    )

    return ClaudeCodeHooks(config=hooks_config)

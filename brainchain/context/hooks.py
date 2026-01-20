"""
Context management hooks for workflow integration.

Integrates context monitoring and compression into the workflow execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Any

from .monitor import ContextMonitor, ContextAction, ThresholdConfig
from .compressor import Compressor, CompressionConfig
from .counter import TokenCounter

if TYPE_CHECKING:
    from ..session.models import Session, Message


@dataclass
class ContextHooksConfig:
    """Configuration for context hooks."""

    # Enable automatic compression
    auto_compress: bool = True

    # Thresholds
    remind_threshold: float = 0.70
    compress_threshold: float = 0.85
    compact_threshold: float = 0.95

    # Compression settings
    keep_recent_messages: int = 10

    # Callbacks
    on_remind: Callable[[float], None] | None = None
    on_compress: Callable[[int], None] | None = None
    on_compact: Callable[[], None] | None = None


class ContextHooks:
    """
    Hooks for context management during workflow execution.

    Integrates with workflow.py to:
    1. Check context before each step
    2. Trigger compression when needed
    3. Provide usage feedback
    """

    def __init__(
        self,
        config: ContextHooksConfig | None = None,
        model: str = "default",
    ):
        """
        Initialize context hooks.

        Args:
            config: Hooks configuration
            model: Model name for token counting
        """
        self.config = config or ContextHooksConfig()

        # Initialize components
        self.counter = TokenCounter(model=model)
        self.monitor = ContextMonitor(
            counter=self.counter,
            thresholds=ThresholdConfig(
                remind=self.config.remind_threshold,
                compress=self.config.compress_threshold,
                compact=self.config.compact_threshold,
            ),
        )
        self.compressor = Compressor(
            config=CompressionConfig(
                keep_recent=self.config.keep_recent_messages,
            )
        )

        # Track state
        self._messages: list["Message"] = []
        self._compression_count = 0

    def set_messages(self, messages: list["Message"]) -> None:
        """Update the message list to monitor."""
        self._messages = messages

    def before_step(self, session: "Session") -> dict[str, Any]:
        """
        Hook called before each workflow step.

        Args:
            session: Current session

        Returns:
            Status dict with any actions taken
        """
        if not self.config.auto_compress:
            return {"action": "none", "usage": 0}

        action = self.monitor.check(self._messages)
        usage = self.monitor.get_usage()

        result = {
            "action": action.name.lower(),
            "usage": usage,
            "used_tokens": self.counter.count_messages(self._messages),
            "limit_tokens": self.counter.get_limit(),
        }

        if action == ContextAction.REMIND:
            self._handle_remind(usage)
        elif action == ContextAction.COMPRESS:
            result["compressed"] = self._handle_compress()
        elif action == ContextAction.COMPACT:
            result["compacted"] = self._handle_compact(session)

        return result

    def after_step(self, session: "Session", new_messages: list["Message"]) -> None:
        """
        Hook called after each workflow step.

        Args:
            session: Current session
            new_messages: Messages added during the step
        """
        # Add new messages to tracking
        self._messages.extend(new_messages)

        # Optionally prune tool outputs
        if len(self._messages) > 30:
            self._messages = self.compressor.prune_tool_outputs(self._messages)

    def get_status(self) -> dict[str, Any]:
        """Get current context status."""
        return self.monitor.get_status(self._messages)

    def get_usage_display(self) -> str:
        """Get formatted usage display."""
        return self.counter.format_usage(self._messages)

    def _handle_remind(self, usage: float) -> None:
        """Handle remind action."""
        if self.config.on_remind:
            self.config.on_remind(usage)

    def _handle_compress(self) -> int:
        """
        Handle compression action.

        Returns:
            Number of messages compressed
        """
        original_count = len(self._messages)

        remaining, summary = self.compressor.summarize_messages(self._messages)

        if summary:
            self._messages = [summary] + remaining
            self._compression_count += 1

            if self.config.on_compress:
                self.config.on_compress(original_count - len(remaining))

        return original_count - len(self._messages)

    def _handle_compact(self, session: "Session") -> bool:
        """
        Handle compaction action.

        Returns:
            True if compaction was performed
        """
        _, compacted_messages = self.compressor.compact_session(
            session, self._messages
        )

        self._messages = compacted_messages
        self.monitor.reset()

        if self.config.on_compact:
            self.config.on_compact()

        return True


def create_hooks_from_config(config: dict[str, Any], model: str = "default") -> ContextHooks:
    """
    Create ContextHooks from config dictionary.

    Args:
        config: Configuration dict (from config.toml [context] section)
        model: Model name for token counting

    Returns:
        Configured ContextHooks instance
    """
    hooks_config = ContextHooksConfig(
        auto_compress=config.get("auto_compress", True),
        remind_threshold=config.get("remind_threshold", 0.70),
        compress_threshold=config.get("compress_threshold", 0.85),
        compact_threshold=config.get("compact_threshold", 0.95),
        keep_recent_messages=config.get("keep_recent_messages", 10),
    )

    return ContextHooks(config=hooks_config, model=model)

"""
Context monitoring and threshold detection.

Monitors context usage and triggers actions at configured thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from .counter import TokenCounter

if TYPE_CHECKING:
    from ..session.models import Message


class ContextAction(Enum):
    """Actions to take based on context usage."""

    NONE = auto()      # No action needed
    REMIND = auto()    # Remind that there's still headroom
    COMPRESS = auto()  # Compress old messages
    COMPACT = auto()   # Full session compaction


@dataclass
class ThresholdConfig:
    """Configuration for context thresholds."""

    remind: float = 0.70      # 70% - reminder
    compress: float = 0.85    # 85% - pre-compression
    compact: float = 0.95     # 95% - full compaction

    def validate(self) -> None:
        """Validate threshold values."""
        if not (0 < self.remind < self.compress < self.compact <= 1.0):
            raise ValueError(
                "Thresholds must be: 0 < remind < compress < compact <= 1.0"
            )


class ContextMonitor:
    """
    Monitors context usage and triggers appropriate actions.

    Implements oh-my-opencode style context anxiety management:
    - 70%: Remind agent there's still headroom
    - 85%: Pre-compress old messages
    - 95%: Full session compaction
    """

    def __init__(
        self,
        counter: TokenCounter | None = None,
        thresholds: ThresholdConfig | None = None,
    ):
        """
        Initialize context monitor.

        Args:
            counter: Token counter instance
            thresholds: Threshold configuration
        """
        self.counter = counter or TokenCounter()
        self.thresholds = thresholds or ThresholdConfig()
        self.thresholds.validate()

        # Track last action to avoid repeated triggers
        self._last_action: ContextAction = ContextAction.NONE
        self._last_usage: float = 0.0

    def check(self, messages: list["Message"]) -> ContextAction:
        """
        Check context usage and determine required action.

        Args:
            messages: Current session messages

        Returns:
            ContextAction to take
        """
        usage = self.counter.usage_percent(messages)
        self._last_usage = usage

        # Determine action based on thresholds
        if usage >= self.thresholds.compact:
            action = ContextAction.COMPACT
        elif usage >= self.thresholds.compress:
            action = ContextAction.COMPRESS
        elif usage >= self.thresholds.remind:
            action = ContextAction.REMIND
        else:
            action = ContextAction.NONE

        # Only return action if it's new or more severe
        if action.value > self._last_action.value:
            self._last_action = action
            return action

        return ContextAction.NONE

    def get_usage(self) -> float:
        """Get last calculated usage percentage."""
        return self._last_usage

    def get_status(self, messages: list["Message"]) -> dict:
        """
        Get detailed status information.

        Args:
            messages: Current session messages

        Returns:
            Status dictionary with usage details
        """
        usage = self.counter.usage_percent(messages)
        used_tokens = self.counter.count_messages(messages)
        limit = self.counter.get_limit()
        remaining = self.counter.remaining_tokens(messages)

        return {
            "usage_percent": usage,
            "used_tokens": used_tokens,
            "limit_tokens": limit,
            "remaining_tokens": remaining,
            "message_count": len(messages),
            "status": self._get_status_label(usage),
        }

    def _get_status_label(self, usage: float) -> str:
        """Get human-readable status label."""
        if usage >= self.thresholds.compact:
            return "critical"
        elif usage >= self.thresholds.compress:
            return "high"
        elif usage >= self.thresholds.remind:
            return "moderate"
        elif usage >= 0.5:
            return "normal"
        else:
            return "low"

    def reset(self) -> None:
        """Reset monitor state."""
        self._last_action = ContextAction.NONE
        self._last_usage = 0.0

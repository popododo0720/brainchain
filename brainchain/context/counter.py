"""
Token counting utilities for context management.

Provides approximate token counting for various AI models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..session.models import Session, Message


@dataclass
class ModelLimits:
    """Token limits for different models."""

    # Model name -> max context tokens
    LIMITS: dict[str, int] = None

    def __post_init__(self):
        if self.LIMITS is None:
            self.LIMITS = {
                # Claude models
                "claude-opus": 200_000,
                "claude-sonnet": 200_000,
                "claude-haiku": 200_000,
                "opus": 200_000,
                "sonnet": 200_000,
                "haiku": 200_000,
                # OpenAI/Codex models
                "gpt-5.2": 128_000,
                "gpt-4": 128_000,
                "gpt-4o": 128_000,
                "codex": 128_000,
                # Default
                "default": 100_000,
            }

    def get_limit(self, model: str) -> int:
        """Get token limit for a model."""
        if self.LIMITS is None:
            self.__post_init__()
        return self.LIMITS.get(model, self.LIMITS.get("default", 100_000))


class TokenCounter:
    """
    Token counter for context management.

    Uses a simple heuristic: ~4 characters per token.
    This is a rough approximation that works reasonably well
    for most text without requiring external tokenizers.
    """

    # Characters per token (approximate)
    CHARS_PER_TOKEN = 4

    def __init__(self, model: str = "default"):
        """
        Initialize token counter.

        Args:
            model: Model name for determining token limits
        """
        self.model = model
        self.limits = ModelLimits()

    def count(self, text: str) -> int:
        """
        Count approximate tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Approximate token count
        """
        if not text:
            return 0
        return len(text) // self.CHARS_PER_TOKEN

    def count_messages(self, messages: list["Message"]) -> int:
        """
        Count total tokens across messages.

        Args:
            messages: List of Message objects

        Returns:
            Total approximate token count
        """
        total = 0
        for msg in messages:
            # Count content
            total += self.count(msg.content)
            # Add overhead for role, metadata (~10 tokens per message)
            total += 10
        return total

    def get_limit(self) -> int:
        """Get token limit for current model."""
        return self.limits.get_limit(self.model)

    def usage_percent(self, messages: list["Message"]) -> float:
        """
        Calculate context usage as percentage.

        Args:
            messages: List of Message objects

        Returns:
            Usage percentage (0.0 to 1.0+)
        """
        used = self.count_messages(messages)
        limit = self.get_limit()
        return used / limit if limit > 0 else 0.0

    def remaining_tokens(self, messages: list["Message"]) -> int:
        """
        Calculate remaining available tokens.

        Args:
            messages: List of Message objects

        Returns:
            Remaining tokens (can be negative if over limit)
        """
        used = self.count_messages(messages)
        limit = self.get_limit()
        return limit - used

    def format_usage(self, messages: list["Message"]) -> str:
        """
        Format usage as human-readable string.

        Args:
            messages: List of Message objects

        Returns:
            Formatted string like "45,000 / 200,000 (22%)"
        """
        used = self.count_messages(messages)
        limit = self.get_limit()
        percent = (used / limit * 100) if limit > 0 else 0
        return f"{used:,} / {limit:,} ({percent:.0f}%)"

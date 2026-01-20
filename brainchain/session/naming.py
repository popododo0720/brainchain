"""
Session naming utilities.

Provides automatic session name generation from prompts.
"""

from __future__ import annotations

import re
import subprocess
from typing import Any


class SessionNamer:
    """
    Generates human-readable names for sessions.

    Uses rules or AI to create concise, descriptive names
    from the initial prompt.
    """

    # Common words to strip
    STRIP_WORDS = {
        "please", "can", "you", "help", "me", "i", "want", "to",
        "need", "would", "like", "could", "should", "the", "a", "an",
        "this", "that", "it", "is", "are", "was", "were", "be",
    }

    # Action words to keep
    ACTION_WORDS = {
        "create", "add", "implement", "fix", "update", "delete",
        "remove", "refactor", "build", "make", "write", "design",
        "setup", "configure", "deploy", "test", "debug", "optimize",
    }

    def __init__(
        self,
        max_length: int = 30,
        use_ai: bool = False,
        ai_agent: str = "claude-haiku",
    ):
        """
        Initialize session namer.

        Args:
            max_length: Maximum name length
            use_ai: Whether to use AI for naming
            ai_agent: Agent to use for AI naming
        """
        self.max_length = max_length
        self.use_ai = use_ai
        self.ai_agent = ai_agent

    def generate_name(self, prompt: str) -> str:
        """
        Generate a session name from a prompt.

        Args:
            prompt: Initial session prompt

        Returns:
            Generated session name
        """
        if not prompt or not prompt.strip():
            return "Unnamed Session"

        if self.use_ai:
            name = self._generate_ai_name(prompt)
            if name:
                return self.slugify(name)

        return self._generate_rule_based_name(prompt)

    def slugify(self, name: str, max_len: int | None = None) -> str:
        """
        Clean and truncate a name.

        Args:
            name: Raw name string
            max_len: Maximum length (uses self.max_length if None)

        Returns:
            Cleaned name
        """
        max_len = max_len or self.max_length

        # Remove special characters except spaces and hyphens
        name = re.sub(r"[^\w\s\-]", "", name)

        # Normalize whitespace
        name = " ".join(name.split())

        # Title case
        name = name.title()

        # Truncate
        if len(name) > max_len:
            # Try to break at word boundary
            truncated = name[:max_len]
            last_space = truncated.rfind(" ")
            if last_space > max_len // 2:
                name = truncated[:last_space]
            else:
                name = truncated

        return name.strip()

    def _generate_rule_based_name(self, prompt: str) -> str:
        """Generate name using rule-based extraction."""
        # Normalize
        text = prompt.lower().strip()

        # Remove quotes and code blocks
        text = re.sub(r'["`\']+', "", text)
        text = re.sub(r"```[\s\S]*?```", "", text)

        # Split into words
        words = text.split()

        # Extract key words
        key_words = []
        found_action = False

        for word in words:
            word = re.sub(r"[^\w]", "", word)

            if not word:
                continue

            # Keep action words
            if word in self.ACTION_WORDS:
                key_words.append(word)
                found_action = True
                continue

            # Skip common words
            if word in self.STRIP_WORDS:
                continue

            # Keep meaningful words
            if len(word) > 2:
                key_words.append(word)

            # Stop after collecting enough
            if len(key_words) >= 5:
                break

        # Build name
        if not key_words:
            # Fallback: first 5 words
            key_words = words[:5]

        name = " ".join(key_words[:4])
        return self.slugify(name)

    def _generate_ai_name(self, prompt: str) -> str | None:
        """Generate name using AI."""
        ai_prompt = f"""Generate a short, descriptive title (3-5 words) for this task.
Return ONLY the title, nothing else.

Task: {prompt[:500]}

Title:"""

        try:
            result = subprocess.run(
                ["claude", "-p", ai_prompt, "--print"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                name = result.stdout.strip()
                # Clean up common AI response patterns
                name = re.sub(r'^(title:|here\'s|")', "", name, flags=re.IGNORECASE)
                name = name.strip('"\'')
                return name[:50]  # Safety limit
        except Exception:
            pass

        return None


def auto_name_session(prompt: str, config: dict[str, Any] | None = None) -> str:
    """
    Convenience function to auto-name a session.

    Args:
        prompt: Initial session prompt
        config: Optional config dict with naming settings

    Returns:
        Generated session name
    """
    config = config or {}

    namer = SessionNamer(
        max_length=config.get("name_max_length", 30),
        use_ai=config.get("auto_name_use_ai", False),
    )

    return namer.generate_name(prompt)

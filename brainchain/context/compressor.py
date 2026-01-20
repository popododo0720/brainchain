"""
Context compression and message summarization.

Provides strategies for reducing context size while preserving
important information.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any
import uuid

if TYPE_CHECKING:
    from ..session.models import Message, Session


@dataclass
class CompressionConfig:
    """Configuration for compression behavior."""

    # Number of recent messages to always keep
    keep_recent: int = 10

    # Maximum messages before triggering compression
    max_messages: int = 50

    # Whether to use AI for summarization
    use_ai_summary: bool = True

    # Agent to use for summarization
    summary_agent: str = "claude-haiku"

    # Prune tool outputs older than N messages
    prune_tool_outputs_after: int = 20


@dataclass
class CompressionResult:
    """Result of a compression operation."""

    original_count: int
    compressed_count: int
    tokens_saved: int
    summary: str | None = None
    pruned_messages: list[str] = field(default_factory=list)


class Compressor:
    """
    Message compression and context reduction.

    Strategies:
    1. Summarize old messages into a single summary message
    2. Prune verbose tool outputs (keep results, remove details)
    3. Full session compaction (create new session with summary)
    """

    def __init__(self, config: CompressionConfig | None = None):
        """
        Initialize compressor.

        Args:
            config: Compression configuration
        """
        self.config = config or CompressionConfig()

    def summarize_messages(
        self,
        messages: list["Message"],
        keep_recent: int | None = None,
    ) -> tuple[list["Message"], "Message"]:
        """
        Summarize old messages into a single summary message.

        Args:
            messages: List of messages to process
            keep_recent: Number of recent messages to keep (overrides config)

        Returns:
            Tuple of (remaining messages, summary message)
        """
        keep = keep_recent or self.config.keep_recent

        if len(messages) <= keep:
            # Nothing to summarize
            return messages, None

        # Split messages
        to_summarize = messages[:-keep]
        to_keep = messages[-keep:]

        # Generate summary
        if self.config.use_ai_summary:
            summary_text = self._generate_ai_summary(to_summarize)
        else:
            summary_text = self._generate_simple_summary(to_summarize)

        # Create summary message
        from ..session.models import Message
        summary_message = Message(
            id=f"summary-{uuid.uuid4().hex[:8]}",
            session_id=messages[0].session_id if messages else "",
            timestamp=datetime.now(),
            role="system",
            content=f"[Session Summary]\n{summary_text}",
            step_index=None,
            task_id=None,
        )

        return to_keep, summary_message

    def prune_tool_outputs(
        self,
        messages: list["Message"],
    ) -> list["Message"]:
        """
        Prune verbose tool outputs from old messages.

        Keeps recent tool outputs intact, but truncates older ones
        to just show the result summary.

        Args:
            messages: List of messages to process

        Returns:
            Messages with pruned tool outputs
        """
        threshold = self.config.prune_tool_outputs_after

        if len(messages) <= threshold:
            return messages

        result = []
        for i, msg in enumerate(messages):
            if i < len(messages) - threshold:
                # Old message - prune if it's a tool output
                if self._is_tool_output(msg):
                    pruned = self._prune_message(msg)
                    result.append(pruned)
                else:
                    result.append(msg)
            else:
                # Recent message - keep as-is
                result.append(msg)

        return result

    def compact_session(
        self,
        session: "Session",
        messages: list["Message"],
    ) -> tuple["Session", list["Message"]]:
        """
        Create a compacted version of the session.

        Generates a comprehensive summary and creates a fresh
        session with the summary as the starting context.

        Args:
            session: Current session
            messages: All session messages

        Returns:
            Tuple of (new session, initial messages with summary)
        """
        # Generate comprehensive summary
        summary_text = self._generate_comprehensive_summary(session, messages)

        # Create summary message
        from ..session.models import Message, Session, SessionStatus

        summary_message = Message(
            id=f"compact-{uuid.uuid4().hex[:8]}",
            session_id=session.id,
            timestamp=datetime.now(),
            role="system",
            content=f"[Compacted Session - Previous: {session.id}]\n\n{summary_text}",
            step_index=None,
            task_id=None,
        )

        # Return the original session with just the summary
        # The caller can decide whether to create a new session
        return session, [summary_message]

    def _generate_ai_summary(self, messages: list["Message"]) -> str:
        """Generate summary using AI agent."""
        # Build context from messages
        context = "\n".join([
            f"[{msg.role}]: {msg.content[:500]}..."
            if len(msg.content) > 500 else f"[{msg.role}]: {msg.content}"
            for msg in messages
        ])

        prompt = f"""Summarize the following conversation history in 2-3 concise paragraphs.
Focus on:
1. Key decisions and outcomes
2. Important code changes or findings
3. Current state and next steps

Conversation:
{context}

Summary:"""

        try:
            # Try to call the summary agent
            result = subprocess.run(
                ["claude", "-p", prompt, "--print"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass

        # Fallback to simple summary
        return self._generate_simple_summary(messages)

    def _generate_simple_summary(self, messages: list["Message"]) -> str:
        """Generate a simple rule-based summary."""
        lines = []
        lines.append(f"Summarized {len(messages)} messages.")

        # Extract key info
        roles = {}
        for msg in messages:
            roles[msg.role] = roles.get(msg.role, 0) + 1

        lines.append(f"Roles: {', '.join(f'{r}({c})' for r, c in roles.items())}")

        # First and last message snippets
        if messages:
            first = messages[0].content[:100]
            lines.append(f"Started with: {first}...")

            last = messages[-1].content[:100]
            lines.append(f"Ended with: {last}...")

        return "\n".join(lines)

    def _generate_comprehensive_summary(
        self,
        session: "Session",
        messages: list["Message"],
    ) -> str:
        """Generate comprehensive summary for session compaction."""
        context = f"""Session: {session.id}
Workflow: {session.workflow_name or 'N/A'}
Initial prompt: {session.initial_prompt}
Messages: {len(messages)}
Status: {session.status.value}

Recent conversation:
"""
        # Include last 10 messages
        for msg in messages[-10:]:
            context += f"\n[{msg.role}]: {msg.content[:300]}..."

        prompt = f"""Create a comprehensive summary of this session for context continuation.

{context}

Include:
1. Original goal/task
2. Key decisions and implementations
3. Current state
4. Any pending items

Summary:"""

        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--print"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass

        return self._generate_simple_summary(messages)

    def _is_tool_output(self, message: "Message") -> bool:
        """Check if message is a tool output."""
        indicators = [
            "```",
            "File:",
            "Output:",
            "Result:",
            "[tool]",
            "function_call",
        ]
        return any(ind in message.content for ind in indicators)

    def _prune_message(self, message: "Message") -> "Message":
        """Create a pruned version of a message."""
        from ..session.models import Message

        # Keep first 200 chars + note
        content = message.content[:200]
        if len(message.content) > 200:
            content += f"\n[... {len(message.content) - 200} chars pruned ...]"

        return Message(
            id=message.id,
            session_id=message.session_id,
            timestamp=message.timestamp,
            role=message.role,
            content=content,
            step_index=message.step_index,
            task_id=message.task_id,
        )

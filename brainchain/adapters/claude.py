"""
Claude Code CLI adapter.
"""

from __future__ import annotations

import re

from .base import BaseAdapter, AdapterConfig


class ClaudeAdapter(BaseAdapter):
    """
    Adapter for Claude Code CLI.

    Usage:
        adapter = ClaudeAdapter()
        result = adapter.run("Create a hello world function")
    """

    name = "claude"
    display_name = "Claude Code"

    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                command="claude",
                args=["-p", "{prompt}", "--print"],
                timeout=300,
            )
        super().__init__(config)

    def build_command(self, prompt: str, **kwargs) -> list[str]:
        """Build claude command."""
        cmd = [self.config.command]

        # Process args, replacing {prompt} placeholder
        for arg in self.config.args:
            if "{prompt}" in arg:
                cmd.append(arg.replace("{prompt}", prompt))
            elif arg == "{prompt}":
                cmd.append(prompt)
            else:
                cmd.append(arg)

        # Add model if specified
        model = kwargs.get("model") or self.config.extra.get("model")
        if model:
            cmd.extend(["--model", model])

        # Add effort level if specified
        effort = kwargs.get("effort") or self.config.extra.get("effort")
        if effort:
            cmd.extend(["--effort", effort])

        # Add allowed tools
        tools = kwargs.get("allowed_tools") or self.config.extra.get("allowed_tools")
        if tools:
            cmd.extend(["--allowedTools", tools])

        return cmd

    def parse_output(self, output: str) -> str:
        """Parse claude output, removing any ANSI codes."""
        # Remove ANSI escape codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        output = ansi_escape.sub('', output)

        # Remove progress indicators
        output = re.sub(r'^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏].*$', '', output, flags=re.MULTILINE)

        return output.strip()


class ClaudeSonnetAdapter(ClaudeAdapter):
    """Claude Code with Sonnet model."""

    name = "claude-sonnet"
    display_name = "Claude Sonnet"

    def __init__(self, config: AdapterConfig | None = None):
        super().__init__(config)
        self.config.extra["model"] = "sonnet"


class ClaudeOpusAdapter(ClaudeAdapter):
    """Claude Code with Opus model."""

    name = "claude-opus"
    display_name = "Claude Opus"

    def __init__(self, config: AdapterConfig | None = None):
        super().__init__(config)
        self.config.extra["model"] = "opus"


class ClaudeHaikuAdapter(ClaudeAdapter):
    """Claude Code with Haiku model."""

    name = "claude-haiku"
    display_name = "Claude Haiku"

    def __init__(self, config: AdapterConfig | None = None):
        super().__init__(config)
        self.config.extra["model"] = "haiku"

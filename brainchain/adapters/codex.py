"""
Codex CLI adapter.
"""

from __future__ import annotations

import re

from .base import BaseAdapter, AdapterConfig


class CodexAdapter(BaseAdapter):
    """
    Adapter for Codex CLI (OpenAI).

    Usage:
        adapter = CodexAdapter()
        result = adapter.run("Implement a binary search function")
    """

    name = "codex"
    display_name = "Codex CLI"

    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                command="codex",
                args=["exec", "{prompt}", "--full-auto"],
                timeout=300,
            )
        super().__init__(config)

    def build_command(self, prompt: str, **kwargs) -> list[str]:
        """Build codex command."""
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
            cmd.extend(["-m", model])

        # Add reasoning effort
        reasoning = kwargs.get("reasoning_effort") or self.config.extra.get("reasoning_effort")
        if reasoning:
            cmd.extend(["-c", f'model_reasoning_effort="{reasoning}"'])

        # Skip git repo check
        if kwargs.get("skip_git") or self.config.extra.get("skip_git"):
            cmd.append("--skip-git-repo-check")

        return cmd

    def parse_output(self, output: str) -> str:
        """Parse codex output."""
        # Remove ANSI escape codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        output = ansi_escape.sub('', output)

        return output.strip()


class CodexGPT5Adapter(CodexAdapter):
    """Codex with GPT-5.2 model."""

    name = "codex-gpt5"
    display_name = "Codex (GPT-5.2)"

    def __init__(self, config: AdapterConfig | None = None):
        super().__init__(config)
        self.config.extra["model"] = "gpt-5.2"


class CodexCoderAdapter(CodexAdapter):
    """Codex with GPT-5.2-codex model."""

    name = "codex-coder"
    display_name = "Codex Coder"

    def __init__(self, config: AdapterConfig | None = None):
        super().__init__(config)
        self.config.extra["model"] = "gpt-5.2-codex"

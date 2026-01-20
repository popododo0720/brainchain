"""
Base adapter class for CLI integrations.
"""

from __future__ import annotations

import asyncio
import subprocess
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator


@dataclass
class AdapterConfig:
    """Configuration for an adapter."""

    command: str  # CLI command (e.g., "claude", "aider")
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout: int = 300
    cwd: str | None = None

    # Streaming options
    stream_output: bool = True

    # Extra options
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterResult:
    """Result from adapter execution."""

    success: bool
    output: str = ""
    error: str | None = None
    exit_code: int = 0
    duration_ms: int = 0

    # Metadata
    adapter: str = ""
    command_run: str = ""


class BaseAdapter(ABC):
    """
    Base class for CLI adapters.

    Subclass and implement:
    - name: Adapter identifier
    - build_command(): Build the CLI command
    - parse_output(): Parse CLI output
    """

    name: str = "base"
    display_name: str = "Base Adapter"

    def __init__(self, config: AdapterConfig | None = None):
        self.config = config or AdapterConfig(command=self.name)
        self._process: subprocess.Popen | None = None

    @classmethod
    def is_available(cls) -> bool:
        """Check if the CLI tool is installed."""
        return shutil.which(cls.name) is not None

    @abstractmethod
    def build_command(self, prompt: str, **kwargs) -> list[str]:
        """
        Build the command to execute.

        Args:
            prompt: User prompt
            **kwargs: Additional options

        Returns:
            Command as list of strings
        """
        pass

    def parse_output(self, output: str) -> str:
        """
        Parse and clean CLI output.

        Override for adapter-specific parsing.

        Args:
            output: Raw output from CLI

        Returns:
            Cleaned output
        """
        return output

    def run(self, prompt: str, cwd: str | None = None, **kwargs) -> AdapterResult:
        """
        Run the CLI tool synchronously.

        Args:
            prompt: User prompt
            cwd: Working directory
            **kwargs: Additional options

        Returns:
            Adapter result
        """
        import time
        start_time = time.time()

        cmd = self.build_command(prompt, **kwargs)
        cmd_str = " ".join(cmd)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                cwd=cwd or self.config.cwd,
                env={**subprocess.os.environ, **self.config.env} if self.config.env else None,
            )

            duration_ms = int((time.time() - start_time) * 1000)
            output = self.parse_output(result.stdout)

            return AdapterResult(
                success=result.returncode == 0,
                output=output,
                error=result.stderr if result.returncode != 0 else None,
                exit_code=result.returncode,
                duration_ms=duration_ms,
                adapter=self.name,
                command_run=cmd_str,
            )

        except subprocess.TimeoutExpired:
            return AdapterResult(
                success=False,
                error=f"Command timed out after {self.config.timeout}s",
                adapter=self.name,
                command_run=cmd_str,
            )
        except Exception as e:
            return AdapterResult(
                success=False,
                error=str(e),
                adapter=self.name,
                command_run=cmd_str,
            )

    async def run_async(
        self,
        prompt: str,
        cwd: str | None = None,
        **kwargs,
    ) -> AdapterResult:
        """
        Run the CLI tool asynchronously.

        Args:
            prompt: User prompt
            cwd: Working directory
            **kwargs: Additional options

        Returns:
            Adapter result
        """
        import time
        start_time = time.time()

        cmd = self.build_command(prompt, **kwargs)
        cmd_str = " ".join(cmd)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or self.config.cwd,
                env={**subprocess.os.environ, **self.config.env} if self.config.env else None,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                return AdapterResult(
                    success=False,
                    error=f"Command timed out after {self.config.timeout}s",
                    adapter=self.name,
                    command_run=cmd_str,
                )

            duration_ms = int((time.time() - start_time) * 1000)
            output = self.parse_output(stdout.decode())

            return AdapterResult(
                success=process.returncode == 0,
                output=output,
                error=stderr.decode() if process.returncode != 0 else None,
                exit_code=process.returncode or 0,
                duration_ms=duration_ms,
                adapter=self.name,
                command_run=cmd_str,
            )

        except Exception as e:
            return AdapterResult(
                success=False,
                error=str(e),
                adapter=self.name,
                command_run=cmd_str,
            )

    async def stream(
        self,
        prompt: str,
        cwd: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream output from the CLI tool.

        Args:
            prompt: User prompt
            cwd: Working directory
            **kwargs: Additional options

        Yields:
            Output chunks
        """
        cmd = self.build_command(prompt, **kwargs)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd or self.config.cwd,
            env={**subprocess.os.environ, **self.config.env} if self.config.env else None,
        )

        self._process = process

        try:
            while True:
                if process.stdout is None:
                    break

                line = await process.stdout.readline()
                if not line:
                    break

                yield line.decode()

            await process.wait()
        finally:
            self._process = None

    def cancel(self) -> None:
        """Cancel running process."""
        if self._process:
            self._process.terminate()

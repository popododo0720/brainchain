"""
Task execution engine for Brainchain.

Handles:
- Single task execution
- Parallel task execution with ThreadPoolExecutor
- CLI command building for different AI agents
- Retry logic with configurable policy
- Session tracking and tool invocation recording
"""

import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from .exceptions import RoleNotFoundError, TaskTimeoutError
from .ui import ProgressUI

if TYPE_CHECKING:
    from .session import SessionManager
    from .mcp import ToolRegistry

__all__ = [
    "Executor",
    "TaskResult",
    "build_cli_command",
]


class TaskResult:
    """Result of a task execution."""

    def __init__(
        self,
        task_id: str | None = None,
        role: str | None = None,
        agent: str | None = None,
        success: bool = False,
        output: str = "",
        error: str | None = None,
        duration: float = 0.0,
        retries: int = 0,
    ):
        self.task_id = task_id
        self.role = role
        self.agent = agent
        self.success = success
        self.output = output
        self.error = error
        self.duration = duration
        self.retries = retries

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.task_id,
            "role": self.role,
            "agent": self.agent,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration": round(self.duration, 2),
            "retries": self.retries,
        }

    @classmethod
    def from_error(cls, task_id: str | None, error: str) -> "TaskResult":
        """Create a failed result from an error message."""
        return cls(task_id=task_id, success=False, error=error)


def build_cli_command(agent_config: dict[str, Any], prompt: str) -> list[str]:
    """
    Build CLI command for an AI agent.

    Supports:
    - Claude CLI (claude)
    - Codex CLI (codex)
    - Custom CLI via args template

    Args:
        agent_config: Agent configuration from config.toml
        prompt: Full prompt text to send

    Returns:
        Command as list of arguments
    """
    cmd = [agent_config["command"]]

    # Add model flag based on CLI type
    if "model" in agent_config:
        if agent_config["command"] == "claude":
            cmd.extend(["--model", agent_config["model"]])
        elif agent_config["command"] == "codex":
            cmd.extend(["-m", agent_config["model"]])

    # Use custom args template or defaults
    if "args" in agent_config:
        substitutions = {
            "prompt": prompt,
            "reasoning_effort": agent_config.get("reasoning_effort", "medium"),
        }
        for arg in agent_config["args"]:
            cmd.append(arg.format(**substitutions))
    else:
        # Default args based on CLI type
        if agent_config["command"] == "claude":
            cmd.extend(["-p", prompt, "--print"])
        elif agent_config["command"] == "codex":
            cmd.extend(["exec", prompt, "--full-auto", "--skip-git-repo-check"])

    return cmd


class Executor:
    """
    Task execution engine with retry and progress support.

    Manages execution of single and parallel tasks with:
    - Configurable retry policy
    - Progress UI updates
    - Timeout handling
    - Session tracking
    - MCP tool integration
    """

    def __init__(
        self,
        config: dict[str, Any],
        prompts: dict[str, str],
        ui: ProgressUI | None = None,
        session_manager: "SessionManager | None" = None,
        tool_registry: "ToolRegistry | None" = None,
    ):
        """
        Initialize executor.

        Args:
            config: Full configuration dictionary
            prompts: Dictionary of role prompts
            ui: Optional progress UI for status updates
            session_manager: Optional session manager for tracking
            tool_registry: Optional MCP tool registry
        """
        self.config = config
        self.prompts = prompts
        self.ui = ui
        self.session_manager = session_manager
        self.tool_registry = tool_registry

        # Retry policy
        retry_policy = config.get("retry_policy", {})
        self.max_retries = retry_policy.get("max_retries", 3)
        self.retry_delay = retry_policy.get("retry_delay", 5)

        # Parallel settings
        parallel_config = config.get("parallel", {})
        self.max_workers = parallel_config.get("max_workers", 5)

    def run_single_task(
        self,
        role: str,
        prompt: str,
        task_id: str | None = None,
        cwd: str | Path | None = None,
        retry: bool = True,
    ) -> TaskResult:
        """
        Execute a single task with optional retry.

        Args:
            role: Role name (must be defined in config)
            prompt: Task prompt/instructions
            task_id: Optional task identifier
            cwd: Working directory for execution
            retry: Whether to retry on failure

        Returns:
            TaskResult with execution outcome
        """
        # Validate role
        if role not in self.config["roles"]:
            available = list(self.config["roles"].keys())
            raise RoleNotFoundError(role, available)

        role_config = self.config["roles"][role]
        agent_name = role_config["agent"]
        agent_config = self.config["agents"][agent_name]

        # Build full prompt with role instructions
        role_prompt = self.prompts.get(role, "")
        full_prompt = f"{role_prompt}\n\n---\n\n{prompt}"

        # Build command
        cmd = build_cli_command(agent_config, full_prompt)
        work_dir = str(cwd) if cwd else os.getcwd()
        timeout = agent_config.get("timeout", 300)

        # Execute with retry
        attempts = 0
        max_attempts = self.max_retries + 1 if retry else 1
        last_error: str | None = None

        while attempts < max_attempts:
            attempts += 1

            if self.ui and task_id:
                if attempts == 1:
                    self.ui.task_started(task_id, role)
                else:
                    self.ui.retry_attempt(task_id, attempts, max_attempts, self.retry_delay)
                    time.sleep(self.retry_delay)

            start_time = time.time()

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=work_dir,
                )

                duration = time.time() - start_time
                success = result.returncode == 0

                if success or attempts >= max_attempts:
                    task_result = TaskResult(
                        task_id=task_id,
                        role=role,
                        agent=agent_name,
                        success=success,
                        output=result.stdout,
                        error=result.stderr if not success else None,
                        duration=duration,
                        retries=attempts - 1,
                    )

                    if self.ui and task_id:
                        self.ui.task_completed(
                            task_id,
                            success,
                            output=result.stdout,
                            error=result.stderr if not success else None,
                        )

                    # Record to session
                    self._record_task_result(task_result, prompt)

                    return task_result

                last_error = result.stderr

            except subprocess.TimeoutExpired:
                duration = time.time() - start_time
                last_error = f"Timeout after {timeout}s"

                if attempts >= max_attempts:
                    task_result = TaskResult.from_error(task_id, last_error)
                    task_result.role = role
                    task_result.agent = agent_name
                    task_result.duration = duration
                    task_result.retries = attempts - 1

                    if self.ui and task_id:
                        self.ui.task_completed(task_id, False, error=last_error)

                    return task_result

            except Exception as e:
                duration = time.time() - start_time
                last_error = str(e)

                if attempts >= max_attempts:
                    task_result = TaskResult.from_error(task_id, last_error)
                    task_result.role = role
                    task_result.agent = agent_name
                    task_result.duration = duration
                    task_result.retries = attempts - 1

                    if self.ui and task_id:
                        self.ui.task_completed(task_id, False, error=last_error)

                    return task_result

        # Should not reach here, but just in case
        return TaskResult.from_error(task_id, last_error or "Unknown error")

    def run_parallel_tasks(
        self,
        tasks: list[dict[str, Any]],
        cwd: str | Path | None = None,
        on_complete: Callable[[TaskResult], None] | None = None,
    ) -> list[TaskResult]:
        """
        Execute multiple tasks in parallel.

        Args:
            tasks: List of task definitions with 'role', 'prompt', and optional 'id'
            cwd: Working directory for all tasks
            on_complete: Optional callback for each completed task

        Returns:
            List of TaskResults in original task order
        """
        if not tasks:
            return []

        if self.ui:
            self.ui.parallel_start(len(tasks))

        max_workers = min(len(tasks), self.max_workers)
        results: dict[str, TaskResult] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_task = {}
            for i, task in enumerate(tasks):
                task_id = task.get("id", f"task{i + 1}")
                future = executor.submit(
                    self.run_single_task,
                    role=task["role"],
                    prompt=task["prompt"],
                    task_id=task_id,
                    cwd=cwd,
                    retry=True,
                )
                future_to_task[future] = task_id

            # Collect results as they complete
            for future in as_completed(future_to_task):
                task_id = future_to_task[future]
                try:
                    result = future.result()
                    results[task_id] = result
                except Exception as e:
                    results[task_id] = TaskResult.from_error(task_id, str(e))

                if on_complete:
                    on_complete(results[task_id])

        # Return results in original order
        ordered_results = []
        for i, task in enumerate(tasks):
            task_id = task.get("id", f"task{i + 1}")
            ordered_results.append(results.get(task_id, TaskResult.from_error(task_id, "Not found")))

        if self.ui:
            self.ui.parallel_summary([r.to_dict() for r in ordered_results])

        return ordered_results

    def run_interactive(
        self,
        agent_name: str,
        system_prompt: str,
        cwd: str | Path | None = None,
    ) -> int:
        """
        Launch an interactive AI agent session.

        Args:
            agent_name: Name of agent to use
            system_prompt: System prompt/context
            cwd: Working directory

        Returns:
            Exit code from subprocess
        """
        if agent_name not in self.config["agents"]:
            if self.ui:
                self.ui.error(f"Unknown agent: {agent_name}")
            return 1

        agent_config = self.config["agents"][agent_name]
        work_dir = str(cwd) if cwd else os.getcwd()

        # Write context to file for reference
        from .compat import get_config_dir
        context_file = get_config_dir() / ".context.md"
        context_file.write_text(system_prompt, encoding="utf-8")

        if self.ui:
            self.ui.info(f"Context: {context_file} ({len(system_prompt)} chars)")

        # Build interactive command
        cmd = [agent_config["command"]]

        if "model" in agent_config:
            if agent_config["command"] == "claude":
                cmd.extend(["--model", agent_config["model"]])
            elif agent_config["command"] == "codex":
                cmd.extend(["-m", agent_config["model"]])

        # Pass system prompt for claude
        if agent_config["command"] == "claude":
            # Truncate if too long
            cmd.extend(["--system-prompt", system_prompt[:10000]])

        if self.ui:
            self.ui.info(f"Running: {' '.join(cmd[:3])}...")

        # Run interactively
        result = subprocess.run(cmd, cwd=work_dir)
        return result.returncode

    def _record_task_result(
        self,
        result: TaskResult,
        prompt: str,
    ) -> None:
        """Record task result to session manager."""
        if not self.session_manager:
            return

        # Record input message
        self.session_manager.add_message(
            session_id=None,  # Uses current session
            role="user",
            content=prompt[:1000],  # Truncate long prompts
            task_id=result.task_id,
        )

        # Record output message
        self.session_manager.add_message(
            session_id=None,
            role="assistant",
            content=result.output[:5000] if result.output else "",
            task_id=result.task_id,
        )

        # Record as tool invocation (CLI type)
        self.session_manager.record_tool_invocation(
            session_id=None,
            tool_type="cli",
            tool_name=f"{result.role}/{result.agent}",
            arguments={"prompt_length": len(prompt)},
            result={"output_length": len(result.output) if result.output else 0},
            success=result.success,
            duration_ms=int(result.duration * 1000),
        )

    def call_mcp_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Call an MCP tool.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result dictionary
        """
        if not self.tool_registry:
            return {"success": False, "error": "MCP tools not configured"}

        start_time = time.time()
        result = self.tool_registry.call_tool_sync(tool_name, arguments)
        duration_ms = int((time.time() - start_time) * 1000)

        # Record to session
        if self.session_manager:
            self.session_manager.record_tool_invocation(
                session_id=None,
                tool_type="mcp",
                tool_name=tool_name,
                arguments=arguments,
                result=result.content,
                success=result.success,
                duration_ms=duration_ms,
            )

        return {
            "success": result.success,
            "content": result.content,
            "error": result.error,
            "duration_ms": duration_ms,
        }

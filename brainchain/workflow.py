"""
Workflow engine for Brainchain.

Implements the automatic chaining of:
Plan → Validate → Implement → Review → Fix

Features:
- Step-by-step execution
- Goto jumps (on_fail, on_success)
- Per-task parallel execution
- Retry with configurable policy
- Dry-run mode
- Session state persistence and resume
"""

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .exceptions import WorkflowError, WorkflowJumpError, WorkflowStepError
from .executor import Executor, TaskResult
from .ui import ProgressUI

if TYPE_CHECKING:
    from .session import SessionManager

__all__ = [
    "WorkflowEngine",
    "WorkflowResult",
    "StepResult",
]


@dataclass
class StepResult:
    """Result of a single workflow step."""

    step_index: int
    role: str
    success: bool
    duration: float = 0.0
    output: str = ""
    error: str | None = None
    task_results: list[TaskResult] = field(default_factory=list)
    skipped: bool = False
    jump_target: str | None = None  # If set, workflow should jump to this role

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "step_index": self.step_index,
            "role": self.role,
            "success": self.success,
            "duration": round(self.duration, 2),
            "output": self.output,
            "error": self.error,
            "task_results": [t.to_dict() for t in self.task_results],
            "skipped": self.skipped,
            "jump_target": self.jump_target,
        }


@dataclass
class WorkflowResult:
    """Result of complete workflow execution."""

    success: bool
    steps_completed: int
    total_steps: int
    step_results: list[StepResult] = field(default_factory=list)
    total_duration: float = 0.0
    final_output: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "steps_completed": self.steps_completed,
            "total_steps": self.total_steps,
            "step_results": [s.to_dict() for s in self.step_results],
            "total_duration": round(self.total_duration, 2),
            "final_output": self.final_output,
            "error": self.error,
        }


class WorkflowEngine:
    """
    Workflow execution engine.

    Manages the complete lifecycle of:
    1. Planning - Generate plan.json
    2. Validation - Validate plan
    3. Implementation - Execute tasks (parallel)
    4. Review - Check results
    5. Fixing - Address issues

    Supports:
    - Conditional jumps (goto:role_name)
    - Per-task parallel execution
    - Output chaining between steps
    - Dry-run mode
    """

    def __init__(
        self,
        config: dict[str, Any],
        prompts: dict[str, str],
        executor: Executor,
        ui: ProgressUI | None = None,
        session_manager: "SessionManager | None" = None,
    ):
        """
        Initialize workflow engine.

        Args:
            config: Full configuration dictionary
            prompts: Dictionary of role prompts
            executor: Task executor instance
            ui: Optional progress UI
            session_manager: Optional session manager for state persistence
        """
        self.config = config
        self.prompts = prompts
        self.executor = executor
        self.ui = ui
        self.session_manager = session_manager

        # Workflow configuration
        workflow_config = config.get("workflow", {})
        self.steps = workflow_config.get("steps", [])
        self.available_roles = list(config["roles"].keys())

        # Build role-to-step-index mapping
        self._role_to_step: dict[str, int] = {}
        for i, step in enumerate(self.steps):
            role = step.get("role")
            if role and role not in self._role_to_step:
                self._role_to_step[role] = i

        # Workflow state
        self._outputs: dict[str, str] = {}  # step outputs
        self._plan: dict[str, Any] | None = None  # parsed plan.json
        self._cwd: Path | None = None

    def run(
        self,
        initial_prompt: str = "",
        cwd: str | Path | None = None,
        dry_run: bool = False,
        max_loops: int = 10,  # Prevent infinite loops
        resume_from_step: int = 0,  # For resuming interrupted workflows
    ) -> WorkflowResult:
        """
        Execute the complete workflow.

        Args:
            initial_prompt: Initial user request/prompt
            cwd: Working directory
            dry_run: If True, print steps without executing
            max_loops: Maximum number of goto jumps to prevent infinite loops
            resume_from_step: Step index to resume from (for recovery)

        Returns:
            WorkflowResult with complete execution details
        """
        if not self.steps:
            return WorkflowResult(
                success=False,
                steps_completed=0,
                total_steps=0,
                error="No workflow steps defined in configuration",
            )

        self._cwd = Path(cwd) if cwd else Path.cwd()
        self._outputs["initial_prompt"] = initial_prompt

        if self.ui:
            self.ui.workflow_start(len(self.steps))

        start_time = time.time()
        step_results: list[StepResult] = []
        current_step = resume_from_step  # Support resume
        loop_count = 0
        visited_steps: dict[int, int] = {}  # Track visits to detect loops

        # If resuming, log it
        if resume_from_step > 0 and self.ui:
            self.ui.info(f"Resuming from step {resume_from_step + 1}")

        while current_step < len(self.steps):
            # Loop detection
            visited_steps[current_step] = visited_steps.get(current_step, 0) + 1
            if visited_steps[current_step] > max_loops:
                if self.ui:
                    self.ui.error(f"Maximum loop count ({max_loops}) exceeded")
                return WorkflowResult(
                    success=False,
                    steps_completed=len(step_results),
                    total_steps=len(self.steps),
                    step_results=step_results,
                    total_duration=time.time() - start_time,
                    error=f"Infinite loop detected at step {current_step + 1}",
                )

            step_config = self.steps[current_step]
            role = step_config.get("role", "unknown")

            if dry_run:
                # Dry run - just print what would happen
                result = self._dry_run_step(current_step, step_config)
                step_results.append(result)
                current_step += 1
                continue

            # Execute step
            try:
                result = self._execute_step(current_step, step_config, initial_prompt)
                step_results.append(result)

                # Save workflow state after each step
                self._save_workflow_state(current_step, step_results)

                # Handle jump if requested
                if result.jump_target:
                    target_step = self._resolve_jump_target(result.jump_target)
                    if target_step is not None:
                        if self.ui:
                            self.ui.workflow_jump(
                                role,
                                result.jump_target.replace("goto:", ""),
                                "on_fail" if not result.success else "on_success",
                            )
                        current_step = target_step
                        loop_count += 1
                        continue

                # Check for failure without jump target
                if not result.success and not result.skipped:
                    if self.ui:
                        self.ui.workflow_summary(False, len(step_results), len(self.steps))
                    return WorkflowResult(
                        success=False,
                        steps_completed=len(step_results),
                        total_steps=len(self.steps),
                        step_results=step_results,
                        total_duration=time.time() - start_time,
                        error=result.error,
                    )

                current_step += 1

            except WorkflowError as e:
                if self.ui:
                    self.ui.error(str(e))
                return WorkflowResult(
                    success=False,
                    steps_completed=len(step_results),
                    total_steps=len(self.steps),
                    step_results=step_results,
                    total_duration=time.time() - start_time,
                    error=str(e),
                )

        # Workflow completed successfully
        total_duration = time.time() - start_time

        if self.ui:
            self.ui.workflow_summary(True, len(step_results), len(self.steps))

        return WorkflowResult(
            success=True,
            steps_completed=len(step_results),
            total_steps=len(self.steps),
            step_results=step_results,
            total_duration=total_duration,
            final_output=self._outputs.get("final", ""),
        )

    def _execute_step(
        self,
        step_index: int,
        step_config: dict[str, Any],
        initial_prompt: str,
    ) -> StepResult:
        """Execute a single workflow step."""
        role = step_config.get("role", "unknown")
        per_task = step_config.get("per_task", False)
        input_file = step_config.get("input")
        output_file = step_config.get("output")
        on_fail = step_config.get("on_fail")
        on_success = step_config.get("on_success")

        start_time = time.time()

        # Build prompt from input
        prompt = self._build_step_prompt(step_config, initial_prompt)

        if self.ui:
            is_parallel = per_task and self._plan and "tasks" in self._plan
            task_count = len(self._plan["tasks"]) if is_parallel else 1
            self.ui.workflow_step_start(
                step_index,
                len(self.steps),
                role,
                is_parallel=is_parallel,
                task_count=task_count,
            )

        # Execute based on per_task setting
        if per_task and self._plan and "tasks" in self._plan:
            # Parallel execution for each task in plan
            result = self._execute_per_task(step_index, role, step_config)
        else:
            # Single task execution
            result = self._execute_single(step_index, role, prompt)

        duration = time.time() - start_time
        result.duration = duration

        # Store output if specified
        if output_file and result.success:
            self._outputs[output_file] = result.output
            # Parse as plan.json if applicable
            if output_file == "plan.json":
                self._parse_plan_output(result.output)

        # Report to UI
        if self.ui:
            if per_task and result.task_results:
                self.ui._write("")  # newline after step start
                self.ui.workflow_step_tasks([t.to_dict() for t in result.task_results])
            else:
                self.ui.workflow_step_completed(
                    result.success,
                    duration,
                    result.error or "",
                )

        # Determine jump target
        if not result.success and on_fail:
            result.jump_target = on_fail
        elif result.success and on_success:
            result.jump_target = on_success

        return result

    def _execute_single(
        self,
        step_index: int,
        role: str,
        prompt: str,
    ) -> StepResult:
        """Execute a single non-parallel step."""
        task_result = self.executor.run_single_task(
            role=role,
            prompt=prompt,
            task_id=f"step{step_index + 1}",
            cwd=self._cwd,
            retry=True,
        )

        success = task_result.success

        # Check for validation verdict in output
        if success and role in ("plan_validator", "code_reviewer"):
            success = self._check_verdict(task_result.output)

        return StepResult(
            step_index=step_index,
            role=role,
            success=success,
            output=task_result.output,
            error=task_result.error,
            task_results=[task_result],
        )

    def _execute_per_task(
        self,
        step_index: int,
        role: str,
        step_config: dict[str, Any],
    ) -> StepResult:
        """Execute step for each task in the plan (parallel)."""
        if not self._plan or "tasks" not in self._plan:
            return StepResult(
                step_index=step_index,
                role=role,
                success=False,
                error="No plan available for per_task execution",
            )

        tasks = self._plan["tasks"]
        parallel_tasks = []

        for task in tasks:
            task_id = task.get("id", f"task{len(parallel_tasks) + 1}")
            task_prompt = self._build_task_prompt(task, step_config)
            parallel_tasks.append({
                "id": task_id,
                "role": role,
                "prompt": task_prompt,
            })

        # Execute in parallel
        task_results = self.executor.run_parallel_tasks(
            tasks=parallel_tasks,
            cwd=self._cwd,
        )

        # Aggregate results
        all_success = all(r.success for r in task_results)
        combined_output = "\n---\n".join(r.output for r in task_results if r.output)
        errors = [r.error for r in task_results if r.error]

        return StepResult(
            step_index=step_index,
            role=role,
            success=all_success,
            output=combined_output,
            error="; ".join(errors) if errors else None,
            task_results=task_results,
        )

    def _build_step_prompt(
        self,
        step_config: dict[str, Any],
        initial_prompt: str,
    ) -> str:
        """Build prompt for a workflow step."""
        parts = []

        # Add initial prompt for first step
        role = step_config.get("role")
        if role == "planner":
            parts.append(f"User Request:\n{initial_prompt}")

        # Add input from previous step
        input_ref = step_config.get("input")
        if input_ref and input_ref in self._outputs:
            parts.append(f"Input ({input_ref}):\n{self._outputs[input_ref]}")

        # Add plan context if available
        if self._plan and role not in ("planner",):
            parts.append(f"Current Plan:\n```json\n{json.dumps(self._plan, indent=2)}\n```")

        return "\n\n".join(parts) if parts else initial_prompt

    def _build_task_prompt(
        self,
        task: dict[str, Any],
        step_config: dict[str, Any],
    ) -> str:
        """Build prompt for a single task within per_task execution."""
        parts = [
            f"Task ID: {task.get('id', 'unknown')}",
            f"Description: {task.get('description', '')}",
            f"Files: {', '.join(task.get('files', []))}",
        ]

        if task.get("acceptance_criteria"):
            parts.append("Acceptance Criteria:")
            for criterion in task["acceptance_criteria"]:
                parts.append(f"  - {criterion}")

        # Add specs context if available
        if self._plan and "specs" in self._plan:
            parts.append("\nRelevant Specs:")
            for spec in self._plan["specs"]:
                parts.append(f"--- {spec.get('file', 'spec')} ---")
                parts.append(spec.get("content", ""))

        return "\n".join(parts)

    def _parse_plan_output(self, output: str) -> None:
        """Parse plan.json from step output."""
        try:
            # Try to extract JSON from output
            # Look for JSON block in markdown
            json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", output)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try parsing entire output as JSON
                json_str = output

            self._plan = json.loads(json_str)

            # Store for later reference
            if self._cwd:
                plan_file = self._cwd / "plan.json"
                plan_file.write_text(json.dumps(self._plan, indent=2), encoding="utf-8")

        except json.JSONDecodeError:
            # Plan parsing failed, continue without structured plan
            self._plan = None

    def _check_verdict(self, output: str) -> bool:
        """Check if validator/reviewer output indicates success."""
        output_lower = output.lower()

        # Look for explicit verdicts
        if '"verdict"' in output_lower:
            if '"approved"' in output_lower or '"passed"' in output_lower:
                return True
            if '"needs_revision"' in output_lower or '"failed"' in output_lower:
                return False

        # Look for keywords
        if "approved" in output_lower or "passed" in output_lower:
            return True
        if "needs_revision" in output_lower or "failed" in output_lower:
            return False

        # Default to success if no clear verdict
        return True

    def _resolve_jump_target(self, target: str) -> int | None:
        """Resolve goto:role_name to step index."""
        if not target.startswith("goto:"):
            return None

        role_name = target[5:]  # Remove "goto:" prefix

        if role_name not in self._role_to_step:
            if self.ui:
                self.ui.warning(f"Jump target '{role_name}' not found in workflow")
            return None

        return self._role_to_step[role_name]

    def _dry_run_step(
        self,
        step_index: int,
        step_config: dict[str, Any],
    ) -> StepResult:
        """Simulate step execution for dry run."""
        role = step_config.get("role", "unknown")
        per_task = step_config.get("per_task", False)

        if self.ui:
            self.ui.workflow_step_start(
                step_index,
                len(self.steps),
                role,
                is_parallel=per_task,
                task_count=3 if per_task else 1,
            )
            self.ui._write(f" [dry-run]")

        return StepResult(
            step_index=step_index,
            role=role,
            success=True,
            skipped=True,
        )

    def get_workflow_info(self) -> dict[str, Any]:
        """Get information about the configured workflow."""
        steps_info = []
        for i, step in enumerate(self.steps):
            steps_info.append({
                "index": i + 1,
                "role": step.get("role"),
                "input": step.get("input"),
                "output": step.get("output"),
                "per_task": step.get("per_task", False),
                "on_fail": step.get("on_fail"),
                "on_success": step.get("on_success"),
            })

        return {
            "total_steps": len(self.steps),
            "steps": steps_info,
            "available_roles": self.available_roles,
        }

    def _save_workflow_state(
        self,
        current_step: int,
        step_results: list[StepResult],
    ) -> None:
        """
        Save workflow state to session manager.

        Args:
            current_step: Current step index
            step_results: Results from completed steps
        """
        if not self.session_manager:
            return

        self.session_manager.save_workflow_state(
            session_id=None,  # Uses current session
            current_step=current_step,
            step_results=[r.to_dict() for r in step_results],
            plan=self._plan,
            outputs=self._outputs,
        )

    def restore_state(
        self,
        plan: dict[str, Any] | None = None,
        outputs: dict[str, str] | None = None,
    ) -> None:
        """
        Restore workflow state from saved data.

        Args:
            plan: Saved plan data
            outputs: Saved step outputs
        """
        if plan is not None:
            self._plan = plan
        if outputs is not None:
            self._outputs = outputs

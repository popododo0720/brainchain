"""
Hook system for lifecycle events.

Allows plugins to tap into brainchain lifecycle:
- pre_execute: Before an agent executes
- post_execute: After an agent executes
- on_error: When an error occurs
- on_output: Process agent output
- on_input: Process user input
- on_session_start: When a session starts
- on_session_end: When a session ends
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..executor import TaskResult


class HookType(Enum):
    """Types of lifecycle hooks."""

    # Execution hooks
    PRE_EXECUTE = "pre_execute"
    POST_EXECUTE = "post_execute"
    ON_ERROR = "on_error"

    # I/O hooks
    ON_INPUT = "on_input"
    ON_OUTPUT = "on_output"

    # Session hooks
    ON_SESSION_START = "on_session_start"
    ON_SESSION_END = "on_session_end"

    # Workflow hooks
    ON_STEP_START = "on_step_start"
    ON_STEP_END = "on_step_end"

    # Context hooks
    ON_CONTEXT_WARNING = "on_context_warning"  # Context usage high
    ON_CONTEXT_COMPRESS = "on_context_compress"  # Before compression


@dataclass
class HookContext:
    """Context passed to hook handlers."""

    hook_type: HookType
    data: dict = field(default_factory=dict)

    # Execution context
    role: str | None = None
    agent: str | None = None
    prompt: str | None = None

    # Result (for post hooks)
    result: "TaskResult | None" = None
    error: Exception | None = None

    # Session context
    session_id: str | None = None
    cwd: str = ""

    # Can be modified by hooks
    modified_prompt: str | None = None
    modified_output: str | None = None
    should_skip: bool = False  # Skip execution (for pre hooks)
    should_retry: bool = False  # Retry execution (for error hooks)


@dataclass
class Hook:
    """Represents a registered hook."""

    hook_type: HookType
    handler: Callable[[HookContext], HookContext | None]
    priority: int = 100  # Lower = earlier
    name: str = ""
    plugin: str | None = None
    enabled: bool = True


# Decorator storage
_pending_hooks: list[tuple[HookType, Callable, dict]] = []


def hook(
    hook_type: HookType,
    priority: int = 100,
    name: str = "",
) -> Callable:
    """
    Decorator to register a hook.

    Args:
        hook_type: Type of hook
        priority: Execution priority (lower = earlier)
        name: Optional name for the hook

    Example:
        @hook(HookType.PRE_EXECUTE)
        def my_hook(ctx: HookContext) -> HookContext:
            print(f"About to execute: {ctx.role}")
            return ctx
    """
    def decorator(fn: Callable) -> Callable:
        _pending_hooks.append((hook_type, fn, {
            "priority": priority,
            "name": name or fn.__name__,
        }))
        return fn
    return decorator


class HookRegistry:
    """
    Registry for lifecycle hooks.
    """

    def __init__(self):
        self._hooks: dict[HookType, list[Hook]] = {t: [] for t in HookType}

    def register(
        self,
        hook_type: HookType,
        handler: Callable[[HookContext], HookContext | None],
        priority: int = 100,
        name: str = "",
        plugin: str | None = None,
    ) -> Hook:
        """
        Register a hook.

        Args:
            hook_type: Type of hook
            handler: Hook handler function
            priority: Execution priority (lower = earlier)
            name: Optional name
            plugin: Plugin that registered this

        Returns:
            The registered hook
        """
        hook = Hook(
            hook_type=hook_type,
            handler=handler,
            priority=priority,
            name=name or handler.__name__,
            plugin=plugin,
        )

        self._hooks[hook_type].append(hook)

        # Sort by priority
        self._hooks[hook_type].sort(key=lambda h: h.priority)

        return hook

    def unregister(self, hook: Hook) -> bool:
        """
        Unregister a hook.

        Args:
            hook: Hook to remove

        Returns:
            True if removed
        """
        if hook in self._hooks[hook.hook_type]:
            self._hooks[hook.hook_type].remove(hook)
            return True
        return False

    def unregister_by_plugin(self, plugin: str) -> int:
        """
        Unregister all hooks from a plugin.

        Args:
            plugin: Plugin name

        Returns:
            Number of hooks removed
        """
        removed = 0
        for hook_type in HookType:
            original_count = len(self._hooks[hook_type])
            self._hooks[hook_type] = [
                h for h in self._hooks[hook_type]
                if h.plugin != plugin
            ]
            removed += original_count - len(self._hooks[hook_type])
        return removed

    def trigger(
        self,
        hook_type: HookType,
        context: HookContext | None = None,
        **kwargs,
    ) -> HookContext:
        """
        Trigger hooks of a specific type.

        Args:
            hook_type: Type of hook to trigger
            context: Initial context (created if not provided)
            **kwargs: Additional context data

        Returns:
            Final context after all hooks
        """
        if context is None:
            context = HookContext(hook_type=hook_type)

        # Update context with kwargs
        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)
            else:
                context.data[key] = value

        # Execute hooks in priority order
        for hook in self._hooks[hook_type]:
            if not hook.enabled:
                continue

            try:
                result = hook.handler(context)
                if result is not None:
                    context = result

                # Check for early exit
                if context.should_skip:
                    break
            except Exception as e:
                # Log error but continue with other hooks
                context.data["hook_error"] = str(e)

        return context

    def get_hooks(self, hook_type: HookType) -> list[Hook]:
        """Get all hooks of a type."""
        return self._hooks[hook_type].copy()

    def list_all(self) -> dict[str, list[Hook]]:
        """List all registered hooks."""
        return {t.value: hooks for t, hooks in self._hooks.items() if hooks}

    def load_pending(self, plugin_name: str | None = None) -> int:
        """
        Load hooks registered via @hook decorator.

        Args:
            plugin_name: Plugin name to tag hooks with

        Returns:
            Number of hooks loaded
        """
        global _pending_hooks

        loaded = 0
        for hook_type, handler, opts in _pending_hooks:
            self.register(
                hook_type=hook_type,
                handler=handler,
                priority=opts.get("priority", 100),
                name=opts.get("name", ""),
                plugin=plugin_name,
            )
            loaded += 1

        _pending_hooks = []
        return loaded

    # Convenience methods for common hooks

    def pre_execute(
        self,
        role: str,
        agent: str,
        prompt: str,
        **kwargs,
    ) -> HookContext:
        """Trigger pre-execute hooks."""
        return self.trigger(
            HookType.PRE_EXECUTE,
            role=role,
            agent=agent,
            prompt=prompt,
            **kwargs,
        )

    def post_execute(
        self,
        role: str,
        agent: str,
        result: "TaskResult",
        **kwargs,
    ) -> HookContext:
        """Trigger post-execute hooks."""
        return self.trigger(
            HookType.POST_EXECUTE,
            role=role,
            agent=agent,
            result=result,
            **kwargs,
        )

    def on_error(
        self,
        error: Exception,
        role: str | None = None,
        **kwargs,
    ) -> HookContext:
        """Trigger error hooks."""
        return self.trigger(
            HookType.ON_ERROR,
            error=error,
            role=role,
            **kwargs,
        )

    def process_input(self, input_text: str, **kwargs) -> str:
        """Process input through hooks."""
        ctx = self.trigger(
            HookType.ON_INPUT,
            prompt=input_text,
            **kwargs,
        )
        return ctx.modified_prompt if ctx.modified_prompt else input_text

    def process_output(self, output: str, **kwargs) -> str:
        """Process output through hooks."""
        ctx = self.trigger(
            HookType.ON_OUTPUT,
            modified_output=output,
            **kwargs,
        )
        return ctx.modified_output if ctx.modified_output else output

"""
Custom hooks for hello_plugin.
"""

from brainchain.plugins.hooks import HookType, HookContext


def register_hooks(registry):
    """Register plugin hooks."""

    # Log before execution
    registry.register(
        hook_type=HookType.PRE_EXECUTE,
        handler=log_pre_execute,
        priority=50,  # Run early
        name="hello_pre_execute",
        plugin="hello_plugin",
    )

    # Log after execution
    registry.register(
        hook_type=HookType.POST_EXECUTE,
        handler=log_post_execute,
        priority=150,  # Run late
        name="hello_post_execute",
        plugin="hello_plugin",
    )

    # Process output
    registry.register(
        hook_type=HookType.ON_OUTPUT,
        handler=add_emoji_to_output,
        priority=100,
        name="hello_add_emoji",
        plugin="hello_plugin",
    )


def log_pre_execute(ctx: HookContext) -> HookContext:
    """Log before agent execution."""
    print(f"[hello_plugin] Starting execution: {ctx.role} -> {ctx.agent}")
    return ctx


def log_post_execute(ctx: HookContext) -> HookContext:
    """Log after agent execution."""
    if ctx.result:
        status = "SUCCESS" if ctx.result.success else "FAILED"
        print(f"[hello_plugin] Execution finished: {status}")
    return ctx


def add_emoji_to_output(ctx: HookContext) -> HookContext:
    """Add emoji to successful outputs."""
    # Example: Add checkmark to successful completions
    if ctx.modified_output and "completed" in ctx.modified_output.lower():
        ctx.modified_output = f"{ctx.modified_output}"
    return ctx

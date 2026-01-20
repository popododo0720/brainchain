"""
Command-line interface for Brainchain.

Entry point for the brainchain command.

Usage:
    brainchain                          # Launch orchestrator
    brainchain --list                   # List agents and roles
    brainchain --exec planner "..."     # Non-interactive single task
    brainchain --parallel tasks.json    # Parallel execution
    brainchain --workflow "..."         # Run full workflow
    brainchain --init                   # Initialize config

    # Session management
    brainchain --sessions               # List sessions
    brainchain --resume <session_id>    # Resume session
    brainchain --session-info <id>      # Session details

    # MCP tools
    brainchain --mcp-list               # List MCP tools
    brainchain --mcp-call <tool> <json> # Call MCP tool

    # LSP tools
    brainchain --lsp refs <file> <sym>  # Find references
    brainchain --lsp rename <f> <o> <n> # Rename symbol
    brainchain --lsp definition <f> <l> <c> # Go to definition
    brainchain --lsp diagnostics <file> # Get diagnostics
"""

import argparse
import json
import sys
from pathlib import Path

from .compat import get_config_dir
from .config import (
    build_system_context,
    get_lsp_config,
    get_mcp_config,
    get_session_config,
    init_config,
    load_config,
    load_prompts,
)
from .exceptions import BrainchainError
from .executor import Executor
from .session import SessionManager, RecoveryManager, SessionStatus
from .ui import ProgressUI
from .workflow import WorkflowEngine

__all__ = ["main", "create_parser"]


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for brainchain CLI."""
    parser = argparse.ArgumentParser(
        prog="brainchain",
        description="Brainchain - Multi-CLI AI Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
    brainchain --list                   List available agents and roles
    brainchain --exec planner "Create auth system"
                                        Run planner role with prompt
    brainchain --parallel tasks.json    Run multiple tasks in parallel
    brainchain --workflow "Create auth" Run complete workflow

Config: {get_config_dir()}
""",
    )

    # Setup commands
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize configuration in ~/.config/brainchain/",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available agents and roles",
    )

    # Execution modes
    parser.add_argument(
        "--exec",
        nargs=2,
        metavar=("ROLE", "PROMPT"),
        help="Execute a single task non-interactively",
    )
    parser.add_argument(
        "--parallel",
        metavar="FILE",
        help="Run parallel tasks from JSON file (use - for stdin)",
    )
    parser.add_argument(
        "--workflow",
        nargs="?",
        const="",
        metavar="PROMPT",
        help="Run complete workflow with optional initial prompt",
    )

    # Interactive mode
    parser.add_argument(
        "--role",
        metavar="NAME",
        help="Launch interactive session with specific role",
    )

    # Options
    parser.add_argument(
        "--cwd",
        metavar="DIR",
        help="Working directory for task execution",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without running",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    # Session management
    parser.add_argument(
        "--sessions",
        action="store_true",
        help="List all sessions",
    )
    parser.add_argument(
        "--resume",
        metavar="SESSION_ID",
        help="Resume an interrupted session",
    )
    parser.add_argument(
        "--session-info",
        metavar="SESSION_ID",
        help="Show detailed session information",
    )
    parser.add_argument(
        "--name", "-n",
        metavar="NAME",
        help="Session name (for --workflow or --exec)",
    )
    parser.add_argument(
        "--rename",
        nargs=2,
        metavar=("SESSION_ID", "NAME"),
        help="Rename an existing session",
    )

    # TUI mode
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Launch interactive TUI dashboard",
    )
    # MCP tools
    parser.add_argument(
        "--mcp-list",
        action="store_true",
        help="List available MCP tools",
    )
    parser.add_argument(
        "--mcp-call",
        nargs=2,
        metavar=("TOOL", "ARGS_JSON"),
        help="Call an MCP tool with JSON arguments",
    )

    # LSP tools
    parser.add_argument(
        "--lsp",
        nargs="+",
        metavar="CMD",
        help="LSP commands: refs, rename, definition, diagnostics",
    )

    return parser


def cmd_init(args: argparse.Namespace) -> int:
    """Handle --init command."""
    try:
        init_config()
        return 0
    except BrainchainError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_list(config: dict, ui: ProgressUI) -> int:
    """Handle --list command."""
    print("=== Agents ===")
    for name, cfg in config["agents"].items():
        model = cfg.get("model", "default")
        reasoning = cfg.get("reasoning_effort", "-")
        print(f"  {name}: {cfg['command']} -m {model} (reasoning: {reasoning})")

    print("\n=== Roles ===")
    for name, cfg in config["roles"].items():
        print(f"  {name} → {cfg['agent']}")

    # Show workflow if defined
    if "workflow" in config and "steps" in config["workflow"]:
        print("\n=== Workflow Steps ===")
        for i, step in enumerate(config["workflow"]["steps"]):
            role = step.get("role", "unknown")
            per_task = " (parallel)" if step.get("per_task") else ""
            on_fail = f" [fail→{step['on_fail']}]" if step.get("on_fail") else ""
            on_success = f" [success→{step['on_success']}]" if step.get("on_success") else ""
            print(f"  {i + 1}. {role}{per_task}{on_fail}{on_success}")

    print(f"\nConfig: {get_config_dir()}")
    return 0


def cmd_exec(
    args: argparse.Namespace,
    config: dict,
    prompts: dict,
    ui: ProgressUI,
) -> int:
    """Handle --exec command."""
    role, prompt = args.exec
    cwd = args.cwd or Path.cwd()

    executor = Executor(config, prompts, ui if not args.json else None)

    try:
        result = executor.run_single_task(
            role=role,
            prompt=prompt,
            task_id="exec",
            cwd=cwd,
        )

        if args.json:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        else:
            if result.success:
                print(result.output)
            else:
                ui.error(f"Task failed: {result.error}")
                return 1

        return 0 if result.success else 1

    except BrainchainError as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}, indent=2))
        else:
            ui.error(str(e))
        return 1


def cmd_parallel(
    args: argparse.Namespace,
    config: dict,
    prompts: dict,
    ui: ProgressUI,
) -> int:
    """Handle --parallel command."""
    cwd = args.cwd or Path.cwd()

    # Load tasks from file or stdin
    try:
        if args.parallel == "-":
            tasks = json.load(sys.stdin)
        else:
            with open(args.parallel) as f:
                tasks = json.load(f)
    except json.JSONDecodeError as e:
        ui.error(f"Invalid JSON: {e}")
        return 1
    except FileNotFoundError:
        ui.error(f"File not found: {args.parallel}")
        return 1

    if not tasks:
        ui.warning("No tasks to execute")
        return 0

    executor = Executor(config, prompts, ui if not args.json else None)

    if not args.json:
        ui.info(f"Running {len(tasks)} tasks in parallel...")

    results = executor.run_parallel_tasks(tasks, cwd=cwd)

    # Output results
    results_dict = [r.to_dict() for r in results]
    print(json.dumps(results_dict, indent=2, ensure_ascii=False))

    # Return non-zero if any task failed
    all_success = all(r.success for r in results)
    return 0 if all_success else 1


def cmd_workflow(
    args: argparse.Namespace,
    config: dict,
    prompts: dict,
    ui: ProgressUI,
) -> int:
    """Handle --workflow command."""
    cwd = args.cwd or Path.cwd()
    initial_prompt = args.workflow or ""

    # Prompt for input if not provided
    if not initial_prompt and sys.stdin.isatty():
        print("Enter your request (Ctrl+D when done):")
        initial_prompt = sys.stdin.read().strip()

    if not initial_prompt:
        ui.error("No prompt provided. Use: brainchain --workflow 'your request'")
        return 1

    executor = Executor(config, prompts, ui if not args.json else None)
    workflow = WorkflowEngine(config, prompts, executor, ui if not args.json else None)

    # Show workflow info in dry-run
    if args.dry_run:
        info = workflow.get_workflow_info()
        print("\n=== Workflow Plan ===")
        print(f"Total steps: {info['total_steps']}")
        print(f"Available roles: {', '.join(info['available_roles'])}")
        print("\nSteps:")
        for step in info['steps']:
            print(f"  {step['index']}. {step['role']}", end="")
            if step['per_task']:
                print(" (per-task parallel)", end="")
            if step['on_fail']:
                print(f" [fail→{step['on_fail']}]", end="")
            if step['on_success']:
                print(f" [success→{step['on_success']}]", end="")
            print()
        return 0

    # Execute workflow
    result = workflow.run(
        initial_prompt=initial_prompt,
        cwd=cwd,
        dry_run=args.dry_run,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif not result.success:
        ui.error(f"Workflow failed: {result.error}")

    return 0 if result.success else 1


def cmd_interactive(
    args: argparse.Namespace,
    config: dict,
    prompts: dict,
    ui: ProgressUI,
) -> int:
    """Handle interactive mode (default or --role)."""
    cwd = args.cwd or Path.cwd()

    executor = Executor(config, prompts, ui)

    if args.role:
        # Launch specific role
        if args.role not in config["roles"]:
            ui.error(f"Unknown role: '{args.role}'")
            available = ", ".join(config["roles"].keys())
            print(f"Available roles: {available}", file=sys.stderr)
            return 1

        agent_name = config["roles"][args.role]["agent"]
        system_prompt = prompts.get(args.role, "")
        ui.info(f"Launching {args.role} (agent: {agent_name})...")
    else:
        # Launch orchestrator
        agent_name = config["orchestrator"]["agent"]
        system_prompt = build_system_context(config, prompts)
        ui.info(f"Launching orchestrator (agent: {agent_name})...")

    return executor.run_interactive(agent_name, system_prompt, cwd)


def cmd_sessions(
    args: argparse.Namespace,
    config: dict,
    ui: ProgressUI,
) -> int:
    """Handle --sessions command."""
    session_config = get_session_config(config)
    manager = SessionManager(
        db_path=session_config.get("db_path"),
        enabled=session_config.get("enabled", True),
    )

    sessions = manager.list_sessions(limit=20)

    if not sessions:
        print("No sessions found.")
        return 0

    if args.json:
        print(json.dumps([s.to_dict() for s in sessions], indent=2))
        return 0

    print("=== Sessions ===\n")
    for session in sessions:
        status_icon = {
            SessionStatus.ACTIVE: "⏳",
            SessionStatus.COMPLETED: "✓",
            SessionStatus.FAILED: "✗",
            SessionStatus.INTERRUPTED: "⚡",
        }.get(session.status, "?")

        prompt_preview = session.initial_prompt[:50]
        if len(session.initial_prompt) > 50:
            prompt_preview += "..."

        print(f"  {status_icon} [{session.id[:8]}] {session.status.value}")
        print(f"    Prompt: {prompt_preview}")
        print(f"    Updated: {session.updated_at.isoformat()}")
        print()

    return 0


def cmd_session_info(
    args: argparse.Namespace,
    config: dict,
    ui: ProgressUI,
) -> int:
    """Handle --session-info command."""
    session_config = get_session_config(config)
    manager = SessionManager(
        db_path=session_config.get("db_path"),
        enabled=session_config.get("enabled", True),
    )

    info = manager.get_session_info(args.session_info)

    if not info:
        ui.error(f"Session not found: {args.session_info}")
        return 1

    if args.json:
        print(json.dumps(info, indent=2, default=str))
        return 0

    session = info["session"]
    print(f"=== Session {session['id'][:8]} ===\n")
    print(f"Status: {session['status']}")
    print(f"Created: {session['created_at']}")
    print(f"Updated: {session['updated_at']}")
    print(f"CWD: {session['cwd']}")
    print(f"\nInitial Prompt:\n{session['initial_prompt']}")

    messages = info.get("messages", [])
    if messages:
        print(f"\n=== Messages ({len(messages)}) ===")
        for msg in messages[-5:]:  # Show last 5
            print(f"  [{msg['role']}] {msg['content'][:100]}...")

    invocations = info.get("tool_invocations", [])
    if invocations:
        print(f"\n=== Tool Invocations ({len(invocations)}) ===")
        for inv in invocations[-5:]:
            status = "✓" if inv["success"] else "✗"
            print(f"  {status} {inv['tool_type']}/{inv['tool_name']} ({inv['duration_ms']}ms)")

    workflow_state = info.get("workflow_state")
    if workflow_state:
        print(f"\n=== Workflow State ===")
        print(f"Current Step: {workflow_state['current_step']}")
        print(f"Completed Steps: {len(workflow_state['step_results'])}")

    return 0


def cmd_rename(
    args: argparse.Namespace,
    config: dict,
    ui: ProgressUI,
) -> int:
    """Handle --rename command."""
    session_id, new_name = args.rename

    session_config = get_session_config(config)
    manager = SessionManager(
        db_path=session_config.get("db_path"),
        enabled=session_config.get("enabled", True),
    )

    # Check if session exists
    session = manager.get_session(session_id)
    if not session:
        ui.error(f"Session not found: {session_id}")
        return 1

    # Update name
    manager.db.update_session_name(session_id, name=new_name)

    if args.json:
        print(json.dumps({
            "success": True,
            "session_id": session_id,
            "name": new_name,
        }, indent=2))
    else:
        ui.success(f"Renamed session {session_id[:8]} to '{new_name}'")

    return 0


def cmd_tui(
    args: argparse.Namespace,
    config: dict,
    ui: ProgressUI,
) -> int:
    """Handle --tui command."""
    try:
        from .tui import TEXTUAL_AVAILABLE, BrainchainApp
    except ImportError:
        ui.error("TUI not available. Install with: pip install brainchain[tui]")
        return 1

    if not TEXTUAL_AVAILABLE:
        ui.error("Textual not installed. Install with: pip install brainchain[tui]")
        return 1

    try:
        app = BrainchainApp()
        app.run()
        return 0
    except Exception as e:
        ui.error(f"TUI error: {e}")
        return 1


def cmd_resume(
    args: argparse.Namespace,
    config: dict,
    prompts: dict,
    ui: ProgressUI,
) -> int:
    """Handle --resume command."""
    session_config = get_session_config(config)
    manager = SessionManager(
        db_path=session_config.get("db_path"),
        enabled=session_config.get("enabled", True),
    )

    recovery = RecoveryManager(manager)
    resume_data = recovery.prepare_resume(args.resume)

    if not resume_data:
        ui.error(f"Session not found or cannot be resumed: {args.resume}")
        return 1

    ui.info(f"Resuming session {args.resume[:8]}...")

    cwd = args.cwd or resume_data.get("cwd", Path.cwd())
    initial_prompt = resume_data.get("initial_prompt", "")

    executor = Executor(config, prompts, ui if not args.json else None)
    executor.session_manager = manager

    workflow = WorkflowEngine(config, prompts, executor, ui if not args.json else None)
    workflow.session_manager = manager

    # Restore workflow state
    workflow_state = resume_data.get("workflow_state")
    if workflow_state:
        workflow._plan = workflow_state.plan
        workflow._outputs = workflow_state.outputs

    result = workflow.run(
        initial_prompt=initial_prompt,
        cwd=cwd,
        resume_from_step=resume_data.get("resume_from_step", 0),
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif not result.success:
        ui.error(f"Workflow failed: {result.error}")

    return 0 if result.success else 1


def cmd_mcp_list(
    args: argparse.Namespace,
    config: dict,
    ui: ProgressUI,
) -> int:
    """Handle --mcp-list command."""
    try:
        from .mcp import is_mcp_available, ToolRegistry, MCPClient
        from .mcp.servers import load_servers_from_config
    except ImportError:
        ui.error("MCP support not installed. Install with: uv add brainchain[mcp]")
        return 1

    if not is_mcp_available():
        ui.error("MCP package not available. Install with: uv add mcp")
        return 1

    mcp_config = get_mcp_config(config)
    servers = load_servers_from_config(mcp_config)

    if not servers:
        print("No MCP servers configured.")
        print("Add servers to your config.toml [mcp.servers] section.")
        return 0

    registry = ToolRegistry()

    for name, server_config in servers.items():
        if server_config.enabled:
            client = MCPClient(server_config, name=name)
            registry.register_client(name, client)

    # Connect and list tools
    import asyncio

    async def list_tools():
        results = await registry.connect_all()
        connected = [name for name, ok in results.items() if ok]

        if not connected:
            print("No MCP servers connected.")
            return

        tools = await registry.get_all_tools()
        await registry.disconnect_all()
        return tools

    try:
        tools = asyncio.get_event_loop().run_until_complete(list_tools())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        tools = loop.run_until_complete(list_tools())

    if not tools:
        print("No tools available.")
        return 0

    if args.json:
        print(json.dumps([{
            "name": t.name,
            "description": t.description,
            "server": t.server_name,
        } for t in tools], indent=2))
        return 0

    print("=== MCP Tools ===\n")
    for tool in tools:
        print(f"  {tool.name} ({tool.server_name})")
        print(f"    {tool.description[:80]}")
        print()

    return 0


def cmd_mcp_call(
    args: argparse.Namespace,
    config: dict,
    ui: ProgressUI,
) -> int:
    """Handle --mcp-call command."""
    try:
        from .mcp import is_mcp_available, ToolRegistry, MCPClient
        from .mcp.servers import load_servers_from_config
    except ImportError:
        ui.error("MCP support not installed. Install with: uv add brainchain[mcp]")
        return 1

    if not is_mcp_available():
        ui.error("MCP package not available. Install with: uv add mcp")
        return 1

    tool_name, args_json = args.mcp_call

    try:
        tool_args = json.loads(args_json)
    except json.JSONDecodeError as e:
        ui.error(f"Invalid JSON arguments: {e}")
        return 1

    mcp_config = get_mcp_config(config)
    servers = load_servers_from_config(mcp_config)

    registry = ToolRegistry()
    for name, server_config in servers.items():
        if server_config.enabled:
            client = MCPClient(server_config, name=name)
            registry.register_client(name, client)

    import asyncio

    async def call_tool():
        await registry.connect_all()
        result = await registry.call_tool(tool_name, tool_args)
        await registry.disconnect_all()
        return result

    try:
        result = asyncio.get_event_loop().run_until_complete(call_tool())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(call_tool())

    if args.json:
        print(json.dumps({
            "success": result.success,
            "content": result.content,
            "error": result.error,
            "duration_ms": result.duration_ms,
        }, indent=2))
    else:
        if result.success:
            print(result.content)
        else:
            ui.error(f"Tool call failed: {result.error}")

    return 0 if result.success else 1


def cmd_lsp(
    args: argparse.Namespace,
    config: dict,
    ui: ProgressUI,
) -> int:
    """Handle --lsp command."""
    try:
        from .lsp import is_lsp_available, LSPClient, LSPOperations
        from .lsp.servers import get_server_for_file, load_servers_from_config
    except ImportError:
        ui.error("LSP support not installed. Install with: uv add brainchain[lsp]")
        return 1

    if not is_lsp_available():
        ui.error("LSP packages not available. Install with: uv add pygls")
        return 1

    lsp_args = args.lsp
    if not lsp_args:
        ui.error("LSP command required: refs, rename, definition, diagnostics")
        return 1

    cmd = lsp_args[0]
    cmd_args = lsp_args[1:]

    lsp_config = get_lsp_config(config)
    cwd = args.cwd or Path.cwd()

    if cmd == "refs":
        # brainchain --lsp refs <file> <symbol>
        if len(cmd_args) < 2:
            ui.error("Usage: --lsp refs <file> <symbol>")
            return 1
        file_path, symbol = cmd_args[0], cmd_args[1]
        return _lsp_find_refs(file_path, symbol, cwd, lsp_config, args, ui)

    elif cmd == "rename":
        # brainchain --lsp rename <file> <old_name> <new_name> [--dry-run]
        if len(cmd_args) < 3:
            ui.error("Usage: --lsp rename <file> <old_name> <new_name>")
            return 1
        file_path, old_name, new_name = cmd_args[0], cmd_args[1], cmd_args[2]
        dry_run = args.dry_run
        return _lsp_rename(file_path, old_name, new_name, dry_run, cwd, lsp_config, args, ui)

    elif cmd == "definition":
        # brainchain --lsp definition <file> <line> <col>
        if len(cmd_args) < 3:
            ui.error("Usage: --lsp definition <file> <line> <col>")
            return 1
        file_path = cmd_args[0]
        line, col = int(cmd_args[1]), int(cmd_args[2])
        return _lsp_definition(file_path, line, col, cwd, lsp_config, args, ui)

    elif cmd == "diagnostics":
        # brainchain --lsp diagnostics <file>
        if len(cmd_args) < 1:
            ui.error("Usage: --lsp diagnostics <file>")
            return 1
        file_path = cmd_args[0]
        return _lsp_diagnostics(file_path, cwd, lsp_config, args, ui)

    else:
        ui.error(f"Unknown LSP command: {cmd}")
        ui.info("Available commands: refs, rename, definition, diagnostics")
        return 1


def _lsp_find_refs(file_path, symbol, cwd, lsp_config, args, ui):
    """Find references to a symbol."""
    from .lsp import LSPClient, LSPOperations
    from .lsp.servers import get_server_for_file

    server_config = get_server_for_file(file_path)
    if not server_config:
        ui.error(f"No LSP server configured for: {file_path}")
        return 1

    import asyncio

    async def find_refs():
        async with LSPClient(server_config, workspace_root=cwd) as client:
            ops = LSPOperations(client, workspace_root=cwd)
            return ops.find_references(file_path, symbol)

    try:
        refs = asyncio.get_event_loop().run_until_complete(find_refs())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        refs = loop.run_until_complete(find_refs())

    if args.json:
        print(json.dumps(refs, indent=2))
    else:
        print(f"=== References to '{symbol}' ({len(refs)}) ===\n")
        for ref in refs:
            print(f"  {ref['file']}:{ref['line']}:{ref['column']}")

    return 0


def _lsp_rename(file_path, old_name, new_name, dry_run, cwd, lsp_config, args, ui):
    """Rename a symbol."""
    from .lsp import LSPClient, LSPOperations
    from .lsp.servers import get_server_for_file

    server_config = get_server_for_file(file_path)
    if not server_config:
        ui.error(f"No LSP server configured for: {file_path}")
        return 1

    import asyncio

    async def rename():
        async with LSPClient(server_config, workspace_root=cwd) as client:
            ops = LSPOperations(client, workspace_root=cwd)
            return ops.rename_symbol(file_path, old_name, new_name, dry_run=dry_run)

    try:
        result = asyncio.get_event_loop().run_until_complete(rename())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(rename())

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("success"):
            mode = "Would change" if dry_run else "Changed"
            print(f"=== Rename '{old_name}' → '{new_name}' ===\n")
            for file, edits in result.get("changes", {}).items():
                print(f"  {file}: {len(edits)} edit(s)")
            if dry_run:
                print("\n(dry-run mode, no changes applied)")
        else:
            ui.error(result.get("error", "Rename failed"))
            return 1

    return 0


def _lsp_definition(file_path, line, col, cwd, lsp_config, args, ui):
    """Go to definition."""
    from .lsp import LSPClient
    from .lsp.servers import get_server_for_file

    server_config = get_server_for_file(file_path)
    if not server_config:
        ui.error(f"No LSP server configured for: {file_path}")
        return 1

    import asyncio

    async def go_to_def():
        async with LSPClient(server_config, workspace_root=cwd) as client:
            return await client.text_document_definition(file_path, line - 1, col - 1)

    try:
        locations = asyncio.get_event_loop().run_until_complete(go_to_def())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        locations = loop.run_until_complete(go_to_def())

    if args.json:
        print(json.dumps([loc.to_dict() for loc in locations], indent=2))
    else:
        if locations:
            print("=== Definition ===\n")
            for loc in locations:
                print(f"  {loc.uri}:{loc.range.start.line + 1}:{loc.range.start.character + 1}")
        else:
            print("Definition not found.")

    return 0


def _lsp_diagnostics(file_path, cwd, lsp_config, args, ui):
    """Get diagnostics for a file."""
    from .lsp import LSPClient, LSPOperations
    from .lsp.servers import get_server_for_file

    server_config = get_server_for_file(file_path)
    if not server_config:
        ui.error(f"No LSP server configured for: {file_path}")
        return 1

    import asyncio

    async def get_diags():
        async with LSPClient(server_config, workspace_root=cwd) as client:
            ops = LSPOperations(client, workspace_root=cwd)
            return ops.get_diagnostics(file_path)

    try:
        diags = asyncio.get_event_loop().run_until_complete(get_diags())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        diags = loop.run_until_complete(get_diags())

    if args.json:
        print(json.dumps(diags, indent=2))
    else:
        if diags:
            print(f"=== Diagnostics ({len(diags)}) ===\n")
            for d in diags:
                icon = {"error": "✗", "warning": "⚠", "info": "ℹ", "hint": "💡"}.get(d["severity"], "?")
                print(f"  {icon} {d['line']}:{d['column']} {d['message']}")
        else:
            print("No diagnostics found.")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Main entry point for brainchain CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)

    # Handle --init before loading config
    if args.init:
        return cmd_init(args)

    # Create UI
    ui = ProgressUI(verbose=args.verbose, no_color=args.no_color)

    # Load configuration
    try:
        config = load_config()
    except BrainchainError as e:
        ui.error(str(e))
        return 1

    # Handle --list
    if args.list:
        return cmd_list(config, ui)

    # Session management commands (don't need prompts)
    if args.sessions:
        return cmd_sessions(args, config, ui)

    if args.session_info:
        return cmd_session_info(args, config, ui)

    # Session rename
    if args.rename:
        return cmd_rename(args, config, ui)

    # TUI mode
    if args.tui:
        return cmd_tui(args, config, ui)

    # MCP commands (don't need prompts)
    if args.mcp_list:
        return cmd_mcp_list(args, config, ui)

    if args.mcp_call:
        return cmd_mcp_call(args, config, ui)

    # LSP commands (don't need prompts)
    if args.lsp:
        return cmd_lsp(args, config, ui)

    # Load prompts for other commands
    try:
        prompts = load_prompts(config)
    except BrainchainError as e:
        ui.error(str(e))
        return 1

    # Route to appropriate command
    if args.exec:
        return cmd_exec(args, config, prompts, ui)

    if args.parallel:
        return cmd_parallel(args, config, prompts, ui)

    if args.workflow is not None:
        return cmd_workflow(args, config, prompts, ui)

    if args.resume:
        return cmd_resume(args, config, prompts, ui)

    # Default: TUI mode
    return cmd_tui(args, config, ui)


if __name__ == "__main__":
    sys.exit(main())

"""
Configuration loading and validation for Brainchain.

Handles:
- TOML config file loading
- Prompt file loading
- Configuration validation
- Default config initialization
"""

import shutil
import tomllib
from pathlib import Path
from typing import Any

from .compat import get_config_dir, get_default_dir
from .exceptions import (
    ConfigNotFoundError,
    ConfigValidationError,
    PromptNotFoundError,
)

__all__ = [
    "load_config",
    "load_prompts",
    "validate_config",
    "init_config",
    "get_config_path",
    "get_prompts_dir",
    "get_session_config",
    "get_mcp_config",
    "get_lsp_config",
    "MINIMAL_CONFIG",
]


def get_config_path() -> Path:
    """Get path to config.toml file."""
    return get_config_dir() / "config.toml"


def get_prompts_dir() -> Path:
    """Get path to prompts directory."""
    return get_config_dir() / "prompts"


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """
    Load and validate configuration from TOML file.

    Args:
        config_path: Optional custom config path. Uses default if not provided.

    Returns:
        Parsed configuration dictionary

    Raises:
        ConfigNotFoundError: If config file doesn't exist
        ConfigValidationError: If config is invalid
    """
    path = config_path or get_config_path()

    if not path.exists():
        raise ConfigNotFoundError(str(path))

    with open(path, "rb") as f:
        config = tomllib.load(f)

    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    """
    Validate configuration structure and required fields.

    Args:
        config: Configuration dictionary to validate

    Raises:
        ConfigValidationError: If validation fails
    """
    # Required top-level sections
    required_sections = ["orchestrator", "agents", "roles"]
    for section in required_sections:
        if section not in config:
            raise ConfigValidationError(
                f"Missing required section: '{section}'",
                field=section
            )

    # Validate orchestrator
    orchestrator = config["orchestrator"]
    if "agent" not in orchestrator:
        raise ConfigValidationError(
            "Orchestrator must specify 'agent'",
            field="orchestrator.agent"
        )
    if orchestrator["agent"] not in config["agents"]:
        raise ConfigValidationError(
            f"Orchestrator agent '{orchestrator['agent']}' not defined in [agents]",
            field="orchestrator.agent"
        )

    # Validate agents
    for name, agent_config in config["agents"].items():
        if "command" not in agent_config:
            raise ConfigValidationError(
                f"Agent '{name}' must specify 'command'",
                field=f"agents.{name}.command"
            )

    # Validate roles
    for name, role_config in config["roles"].items():
        if "agent" not in role_config:
            raise ConfigValidationError(
                f"Role '{name}' must specify 'agent'",
                field=f"roles.{name}.agent"
            )
        if role_config["agent"] not in config["agents"]:
            raise ConfigValidationError(
                f"Role '{name}' uses undefined agent '{role_config['agent']}'",
                field=f"roles.{name}.agent"
            )
        if "prompt_file" not in role_config:
            raise ConfigValidationError(
                f"Role '{name}' must specify 'prompt_file'",
                field=f"roles.{name}.prompt_file"
            )

    # Validate workflow steps if present
    if "workflow" in config and "steps" in config["workflow"]:
        available_roles = list(config["roles"].keys())
        for i, step in enumerate(config["workflow"]["steps"]):
            if "role" not in step:
                raise ConfigValidationError(
                    f"Workflow step {i + 1} must specify 'role'",
                    field=f"workflow.steps[{i}].role"
                )
            if step["role"] not in available_roles:
                raise ConfigValidationError(
                    f"Workflow step {i + 1} uses undefined role '{step['role']}'",
                    field=f"workflow.steps[{i}].role"
                )

    # Validate session config if present
    if "session" in config:
        _validate_session_config(config["session"])

    # Validate MCP config if present
    if "mcp" in config:
        _validate_mcp_config(config["mcp"])

    # Validate LSP config if present
    if "lsp" in config:
        _validate_lsp_config(config["lsp"])


def _validate_session_config(session_config: dict[str, Any]) -> None:
    """Validate session configuration section."""
    # Validate retention_days if present
    if "retention_days" in session_config:
        retention = session_config["retention_days"]
        if not isinstance(retention, int) or retention < 1:
            raise ConfigValidationError(
                "session.retention_days must be a positive integer",
                field="session.retention_days"
            )


def _validate_mcp_config(mcp_config: dict[str, Any]) -> None:
    """Validate MCP configuration section."""
    # Validate timeout if present
    if "connect_timeout" in mcp_config:
        timeout = mcp_config["connect_timeout"]
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ConfigValidationError(
                "mcp.connect_timeout must be a positive number",
                field="mcp.connect_timeout"
            )

    # Validate servers if present
    if "servers" in mcp_config:
        for name, server in mcp_config["servers"].items():
            if isinstance(server, dict):
                if "command" in server:
                    cmd = server["command"]
                    if not isinstance(cmd, list) or not cmd:
                        raise ConfigValidationError(
                            f"mcp.servers.{name}.command must be a non-empty list",
                            field=f"mcp.servers.{name}.command"
                        )


def _validate_lsp_config(lsp_config: dict[str, Any]) -> None:
    """Validate LSP configuration section."""
    # Validate servers if present
    if "servers" in lsp_config:
        for name, server in lsp_config["servers"].items():
            if isinstance(server, dict):
                if "command" in server:
                    cmd = server["command"]
                    if not isinstance(cmd, list) or not cmd:
                        raise ConfigValidationError(
                            f"lsp.servers.{name}.command must be a non-empty list",
                            field=f"lsp.servers.{name}.command"
                        )


def load_prompts(config: dict[str, Any], config_dir: Path | None = None) -> dict[str, str]:
    """
    Load all prompt files for configured roles.

    Args:
        config: Configuration dictionary
        config_dir: Optional config directory override

    Returns:
        Dictionary mapping role names to prompt content

    Raises:
        PromptNotFoundError: If a prompt file is missing
    """
    base_dir = config_dir or get_config_dir()
    prompts: dict[str, str] = {}

    # Load orchestrator prompt
    if "prompt_file" in config["orchestrator"]:
        orch_path = base_dir / config["orchestrator"]["prompt_file"]
        if not orch_path.exists():
            raise PromptNotFoundError("orchestrator", str(orch_path))
        prompts["orchestrator"] = orch_path.read_text(encoding="utf-8")

    # Load role prompts
    for role_name, role_config in config["roles"].items():
        prompt_path = base_dir / role_config["prompt_file"]
        if not prompt_path.exists():
            raise PromptNotFoundError(role_name, str(prompt_path))
        prompts[role_name] = prompt_path.read_text(encoding="utf-8")

    return prompts


def init_config(force: bool = False) -> None:
    """
    Initialize configuration in the user's config directory.

    Copies default config.toml and prompts/ from package installation.

    Args:
        force: If True, overwrite existing configuration

    Raises:
        ConfigValidationError: If initialization fails
    """
    config_dir = get_config_dir()
    config_file = get_config_path()
    prompts_dir = get_prompts_dir()
    default_dir = get_default_dir()

    # Create config directory
    if not config_dir.exists():
        config_dir.mkdir(parents=True)
        print(f"Created {config_dir}")

    # Copy config.toml
    if not config_file.exists() or force:
        src = default_dir / "config.toml"
        if src.exists():
            shutil.copy(src, config_file)
            print(f"Copied config.toml to {config_file}")
        else:
            # Write minimal config
            config_file.write_text(MINIMAL_CONFIG, encoding="utf-8")
            print(f"Created minimal config at {config_file}")
    else:
        print(f"Config already exists: {config_file}")

    # Copy prompts directory
    if not prompts_dir.exists() or force:
        src = default_dir / "prompts"
        if src.exists() and src.is_dir():
            if prompts_dir.exists():
                shutil.rmtree(prompts_dir)
            shutil.copytree(src, prompts_dir)
            print(f"Copied prompts/ to {prompts_dir}")
        else:
            prompts_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created {prompts_dir} (add prompt files manually)")
    else:
        print(f"Prompts already exist: {prompts_dir}")

    print(f"\nConfig location: {config_dir}")
    print("Edit config.toml and prompts/*.md to customize.")


def build_system_context(config: dict[str, Any], prompts: dict[str, str]) -> str:
    """
    Build the full system context for the orchestrator.

    Combines the orchestrator prompt with role information.

    Args:
        config: Configuration dictionary
        prompts: Dictionary of role prompts

    Returns:
        Complete system context string
    """
    context_parts = [prompts.get("orchestrator", ""), "\n---\n## Available Role Prompts\n"]

    # Role → Agent mapping table
    context_parts.append("\n### Role → Agent Mapping\n")
    context_parts.append("| Role | Agent | Model | Reasoning |")
    context_parts.append("|------|-------|-------|-----------|")
    for role_name, role_config in config["roles"].items():
        agent_name = role_config["agent"]
        agent_cfg = config["agents"][agent_name]
        model = agent_cfg.get("model", "default")
        reasoning = agent_cfg.get("reasoning_effort", "medium")
        context_parts.append(f"| {role_name} | {agent_name} | {model} | {reasoning} |")

    # Parallel execution example
    context_parts.append("\n### Parallel Execution\n")
    context_parts.append("```bash")
    context_parts.append(
        'echo \'[{"role":"implementer","prompt":"Task 1","id":"t1"}]\' | brainchain --parallel -'
    )
    context_parts.append("```\n")

    # Role prompt details
    context_parts.append("\n### Role Prompt Details\n")
    for role_name, role_config in config["roles"].items():
        agent_name = role_config["agent"]
        context_parts.append(f"\n#### {role_name} (uses {agent_name})\n")
        context_parts.append(f"```\n{prompts.get(role_name, '')}\n```\n")

    return "\n".join(context_parts)


def get_session_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get session configuration with defaults.

    Args:
        config: Full configuration dictionary

    Returns:
        Session configuration with defaults applied
    """
    defaults = {
        "enabled": True,
        "db_path": str(get_config_dir() / "sessions.db"),
        "auto_save": True,
        "retention_days": 30,
        "recovery": {
            "auto_detect": True,
            "prompt_resume": True,
        },
    }

    session_config = config.get("session", {})
    result = {**defaults, **session_config}

    # Merge recovery defaults
    if "recovery" in session_config:
        result["recovery"] = {**defaults["recovery"], **session_config["recovery"]}

    return result


def get_mcp_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get MCP configuration with defaults.

    Args:
        config: Full configuration dictionary

    Returns:
        MCP configuration with defaults applied
    """
    defaults = {
        "enabled": True,
        "connect_timeout": 10,
        "servers": {},
    }

    mcp_config = config.get("mcp", {})
    return {**defaults, **mcp_config}


def get_lsp_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get LSP configuration with defaults.

    Args:
        config: Full configuration dictionary

    Returns:
        LSP configuration with defaults applied
    """
    defaults = {
        "enabled": True,
        "auto_start": False,
        "servers": {},
    }

    lsp_config = config.get("lsp", {})
    return {**defaults, **lsp_config}


# Minimal config for bootstrapping
MINIMAL_CONFIG = """# Brainchain Configuration
# See documentation for full options

[orchestrator]
agent = "claude-opus"
prompt_file = "prompts/orchestrator.md"

[agents.claude-opus]
command = "claude"
model = "opus"
args = ["-p", "{prompt}", "--print"]
timeout = 300

[agents.claude-sonnet]
command = "claude"
model = "sonnet"
args = ["-p", "{prompt}", "--print"]
timeout = 300

[agents.codex-gpt5]
command = "codex"
model = "gpt-5.2"
reasoning_effort = "high"
args = ["exec", "{prompt}", "--full-auto", "--skip-git-repo-check", "-c", "model_reasoning_effort=\\"{reasoning_effort}\\""]
timeout = 300

[roles.planner]
agent = "claude-opus"
prompt_file = "prompts/planner.md"

[roles.plan_validator]
agent = "codex-gpt5"
prompt_file = "prompts/plan_validator.md"

[roles.implementer]
agent = "claude-opus"
prompt_file = "prompts/implementer.md"

[roles.code_reviewer]
agent = "codex-gpt5"
prompt_file = "prompts/code_reviewer.md"

[roles.fixer]
agent = "claude-opus"
prompt_file = "prompts/fixer.md"

# Workflow definition
[[workflow.steps]]
role = "planner"
output = "plan.json"

[[workflow.steps]]
role = "plan_validator"
input = "plan.json"
on_fail = "goto:planner"

[[workflow.steps]]
role = "implementer"
input = "plan.json"
per_task = true

[[workflow.steps]]
role = "code_reviewer"
per_task = true
on_fail = "goto:fixer"

[[workflow.steps]]
role = "fixer"
on_success = "goto:code_reviewer"

[retry_policy]
max_retries = 3
retry_delay = 5

[parallel]
max_workers = 5

# Session management
[session]
enabled = true
auto_save = true
retention_days = 30

[session.recovery]
auto_detect = true
prompt_resume = true

# MCP integration (optional)
[mcp]
enabled = false
connect_timeout = 10

# [mcp.servers.filesystem]
# enabled = true
# command = ["npx", "-y", "@modelcontextprotocol/server-filesystem"]
# args = { allowed_paths = ["."] }

# LSP integration (optional)
[lsp]
enabled = false
auto_start = false

# [lsp.servers.python]
# enabled = true
# command = ["pylsp"]
"""

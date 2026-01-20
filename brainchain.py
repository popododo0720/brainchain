#!/usr/bin/env python3
"""
Brainchain - Multi-CLI AI Orchestrator with parallel execution.

Usage:
  brainchain                          # Launch orchestrator
  brainchain --list                   # List agents and roles
  brainchain --exec planner "..."     # Non-interactive single task
  brainchain --parallel tasks.json    # Parallel execution
  brainchain --init                   # Initialize config in ~/.config/brainchain/
"""

import tomllib
import subprocess
import json
import sys
import os
import argparse
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

CONFIG_DIR = Path.home() / ".config" / "brainchain"
CONFIG_FILE = CONFIG_DIR / "config.toml"
PROMPTS_DIR = CONFIG_DIR / "prompts"


def get_default_dir():
    return Path(__file__).parent


def init_config():
    default_dir = get_default_dir()

    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True)
        print(f"Created {CONFIG_DIR}")

    if not CONFIG_FILE.exists():
        src = default_dir / "config.toml"
        if src.exists():
            shutil.copy(src, CONFIG_FILE)
            print(f"Copied config.toml to {CONFIG_FILE}")
        else:
            print(f"Warning: {src} not found, creating minimal config")
            CONFIG_FILE.write_text(MINIMAL_CONFIG)
    else:
        print(f"Config already exists: {CONFIG_FILE}")

    if not PROMPTS_DIR.exists():
        src = default_dir / "prompts"
        if src.exists():
            shutil.copytree(src, PROMPTS_DIR)
            print(f"Copied prompts/ to {PROMPTS_DIR}")
        else:
            PROMPTS_DIR.mkdir(parents=True)
            print(f"Created {PROMPTS_DIR} (add prompt files manually)")
    else:
        print(f"Prompts already exist: {PROMPTS_DIR}")

    print(f"\nConfig location: {CONFIG_DIR}")
    print("Edit config.toml and prompts/*.md to customize.")


def load_config():
    if not CONFIG_FILE.exists():
        print(f"Error: Config not found at {CONFIG_FILE}")
        print("Run 'brainchain --init' to initialize.")
        sys.exit(1)

    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


def load_prompts(config):
    prompts = {}

    orch_prompt_path = CONFIG_DIR / config["orchestrator"]["prompt_file"]
    if not orch_prompt_path.exists():
        print(f"Error: {orch_prompt_path} not found")
        sys.exit(1)
    prompts["orchestrator"] = orch_prompt_path.read_text()

    for role_name, role_config in config["roles"].items():
        prompt_path = CONFIG_DIR / role_config["prompt_file"]
        if not prompt_path.exists():
            print(f"Error: {prompt_path} not found")
            sys.exit(1)
        prompts[role_name] = prompt_path.read_text()

    return prompts


def build_system_context(config, prompts):
    context_parts = [prompts["orchestrator"], "\n---\n## Available Role Prompts\n"]

    context_parts.append("\n### Role → Agent Mapping\n")
    context_parts.append("| Role | Agent | Model | Reasoning |")
    context_parts.append("|------|-------|-------|-----------|")
    for role_name, role_config in config["roles"].items():
        agent_name = role_config["agent"]
        agent_cfg = config["agents"][agent_name]
        model = agent_cfg.get("model", "default")
        reasoning = agent_cfg.get("reasoning_effort", "medium")
        context_parts.append(f"| {role_name} | {agent_name} | {model} | {reasoning} |")

    context_parts.append("\n### Parallel Execution\n")
    context_parts.append("```bash")
    context_parts.append(
        'echo \'[{"role":"implementer","prompt":"Task 1","id":"t1"}]\' | brainchain --parallel -'
    )
    context_parts.append("```\n")

    context_parts.append("\n### Role Prompt Details\n")
    for role_name, role_config in config["roles"].items():
        agent_name = role_config["agent"]
        context_parts.append(f"\n#### {role_name} (uses {agent_name})\n")
        context_parts.append(f"```\n{prompts[role_name]}\n```\n")

    return "\n".join(context_parts)


def build_cli_command(agent_config, prompt):
    cmd = [agent_config["command"]]

    if "model" in agent_config:
        if agent_config["command"] == "claude":
            cmd.extend(["--model", agent_config["model"]])
        elif agent_config["command"] == "codex":
            cmd.extend(["-m", agent_config["model"]])

    if "args" in agent_config:
        substitutions = {
            "prompt": prompt,
            "reasoning_effort": agent_config.get("reasoning_effort", "medium"),
        }
        for arg in agent_config["args"]:
            cmd.append(arg.format(**substitutions))
    else:
        if agent_config["command"] == "claude":
            cmd.extend(["-p", prompt, "--print"])
        elif agent_config["command"] == "codex":
            cmd.extend(["exec", prompt, "--full-auto", "--skip-git-repo-check"])

    return cmd


def run_single_task(config, prompts, role, prompt, task_id=None, cwd=None):
    if role not in config["roles"]:
        return {"id": task_id, "error": f"Unknown role: {role}", "success": False}

    agent_name = config["roles"][role]["agent"]
    agent_config = config["agents"][agent_name]
    role_prompt = prompts[role]
    full_prompt = f"{role_prompt}\n\n---\n\n{prompt}"

    cmd = build_cli_command(agent_config, full_prompt)
    work_dir = cwd or os.getcwd()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=agent_config.get("timeout", 300),
            cwd=work_dir,
        )
        return {
            "id": task_id,
            "role": role,
            "agent": agent_name,
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None,
        }
    except subprocess.TimeoutExpired:
        return {"id": task_id, "error": "Timeout expired", "success": False}
    except Exception as e:
        return {"id": task_id, "error": str(e), "success": False}


def run_parallel_tasks(config, prompts, tasks, cwd=None):
    max_workers = min(len(tasks), config.get("parallel", {}).get("max_workers", 5))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for task in tasks:
            future = executor.submit(
                run_single_task,
                config,
                prompts,
                task["role"],
                task["prompt"],
                task.get("id"),
                cwd,
            )
            futures.append(future)

        results = [f.result() for f in futures]
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Brainchain - Multi-CLI AI Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Config: {CONFIG_DIR}",
    )
    parser.add_argument("--init", action="store_true", help="Initialize config")
    parser.add_argument("--list", action="store_true", help="List agents and roles")
    parser.add_argument("--role", metavar="NAME", help="Launch specific role")
    parser.add_argument(
        "--exec", nargs=2, metavar=("ROLE", "PROMPT"), help="Execute non-interactively"
    )
    parser.add_argument(
        "--parallel",
        metavar="FILE",
        help="Run parallel tasks from JSON (use - for stdin)",
    )
    parser.add_argument("--cwd", metavar="DIR", help="Working directory for tasks")
    args = parser.parse_args()

    if args.init:
        init_config()
        return

    config = load_config()

    if args.list:
        print("=== Agents ===")
        for name, cfg in config["agents"].items():
            model = cfg.get("model", "default")
            reasoning = cfg.get("reasoning_effort", "-")
            print(f"  {name}: {cfg['command']} -m {model} (reasoning: {reasoning})")
        print("\n=== Roles ===")
        for name, cfg in config["roles"].items():
            print(f"  {name} → {cfg['agent']}")
        print(f"\nConfig: {CONFIG_DIR}")
        return

    prompts = load_prompts(config)
    cwd = args.cwd or os.getcwd()

    if args.parallel:
        if args.parallel == "-":
            tasks = json.load(sys.stdin)
        else:
            with open(args.parallel) as f:
                tasks = json.load(f)

        print(f"Running {len(tasks)} tasks in parallel...", file=sys.stderr)
        results = run_parallel_tasks(config, prompts, tasks, cwd)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if args.exec:
        role, prompt = args.exec
        result = run_single_task(config, prompts, role, prompt, task_id="exec", cwd=cwd)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.role:
        if args.role not in config["roles"]:
            print(f"Error: Unknown role '{args.role}'")
            print(f"Available: {', '.join(config['roles'].keys())}")
            return 1
        agent_name = config["roles"][args.role]["agent"]
        system_prompt = prompts[args.role]
        print(f"Launching {args.role} (agent: {agent_name})...")
    else:
        agent_name = config["orchestrator"]["agent"]
        system_prompt = build_system_context(config, prompts)
        print(f"Launching orchestrator (agent: {agent_name})...")

    agent_config = config["agents"][agent_name]

    context_file = CONFIG_DIR / ".context.md"
    context_file.write_text(system_prompt)
    print(f"Context: {context_file} ({len(system_prompt)} chars)")

    cmd = [agent_config["command"]]
    if "model" in agent_config:
        if agent_config["command"] == "claude":
            cmd.extend(["--model", agent_config["model"]])
        elif agent_config["command"] == "codex":
            cmd.extend(["-m", agent_config["model"]])

    if agent_config["command"] == "claude":
        cmd.extend(["--system-prompt", system_prompt[:10000]])

    print(f"Running: {' '.join(cmd[:3])}...")
    subprocess.run(cmd, cwd=cwd)


MINIMAL_CONFIG = """
[orchestrator]
agent = "claude-opus"
prompt_file = "prompts/orchestrator.md"

[agents.claude-opus]
command = "claude"
model = "opus"
args = ["-p", "{prompt}", "--print"]
timeout = 300

[agents.codex-gpt5]
command = "codex"
model = "gpt-5.2"
reasoning_effort = "high"
args = ["exec", "{prompt}", "--full-auto", "--skip-git-repo-check"]
timeout = 300

[roles.planner]
agent = "claude-opus"
prompt_file = "prompts/planner.md"

[roles.implementer]
agent = "claude-opus"
prompt_file = "prompts/implementer.md"

[roles.code_reviewer]
agent = "codex-gpt5"
prompt_file = "prompts/code_reviewer.md"
"""

if __name__ == "__main__":
    main()

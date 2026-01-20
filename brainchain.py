#!/usr/bin/env python3
"""
Brainchain - Multi-CLI AI Orchestrator with parallel execution.

Usage:
  python brainchain.py                     # Launch orchestrator interactively
  python brainchain.py --list              # List agents and roles
  python brainchain.py --role planner      # Launch specific role
  python brainchain.py --exec planner "Create a plan for..."  # Non-interactive
  python brainchain.py --parallel tasks.json  # Parallel execution
"""

import tomllib
import subprocess
import asyncio
import json
import sys
import os
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


def load_config():
    config_path = Path(__file__).parent / "config.toml"
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def load_prompts(config):
    prompts = {}
    base_path = Path(__file__).parent

    orch_prompt_path = base_path / config["orchestrator"]["prompt_file"]
    prompts["orchestrator"] = orch_prompt_path.read_text()

    for role_name, role_config in config["roles"].items():
        prompt_path = base_path / role_config["prompt_file"]
        prompts[role_name] = prompt_path.read_text()

    return prompts


def build_system_context(config, prompts):
    context_parts = [prompts["orchestrator"], "\n---\n## Available Role Prompts\n"]

    context_parts.append("\n### Role → Agent Mapping (from config.toml)\n")
    context_parts.append("| Role | Agent | Model | Reasoning |")
    context_parts.append("|------|-------|-------|-----------|")
    for role_name, role_config in config["roles"].items():
        agent_name = role_config["agent"]
        agent_cfg = config["agents"][agent_name]
        model = agent_cfg.get("model", "default")
        reasoning = agent_cfg.get("reasoning_effort", "medium")
        context_parts.append(f"| {role_name} | {agent_name} | {model} | {reasoning} |")

    context_parts.append("\n### Parallel Execution\n")
    context_parts.append("To run tasks in parallel, create a tasks.json file:")
    context_parts.append("```json")
    context_parts.append(
        '[{"role": "implementer", "prompt": "Task 1...", "id": "task1"},'
    )
    context_parts.append(
        ' {"role": "implementer", "prompt": "Task 2...", "id": "task2"}]'
    )
    context_parts.append("```")
    context_parts.append("Then run: `python brainchain.py --parallel tasks.json`")
    context_parts.append("\nResults are returned as JSON with task IDs.\n")

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
            cmd.extend(["-p", prompt, "--print", "--dangerously-skip-permissions"])
        elif agent_config["command"] == "codex":
            cmd.extend(["exec", prompt, "--full-auto", "--skip-git-repo-check"])

    return cmd


def run_single_task(config, prompts, role, prompt, task_id=None):
    if role not in config["roles"]:
        return {"id": task_id, "error": f"Unknown role: {role}", "success": False}

    agent_name = config["roles"][role]["agent"]
    agent_config = config["agents"][agent_name]
    role_prompt = prompts[role]
    full_prompt = f"{role_prompt}\n\n---\n\n{prompt}"

    cmd = build_cli_command(agent_config, full_prompt)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=agent_config.get("timeout", 300),
            cwd=os.getcwd(),
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


def run_parallel_tasks(config, prompts, tasks):
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = []
        for task in tasks:
            future = executor.submit(
                run_single_task,
                config,
                prompts,
                task["role"],
                task["prompt"],
                task.get("id"),
            )
            futures.append(future)

        results = [f.result() for f in futures]
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Brainchain - Multi-CLI AI Orchestrator"
    )
    parser.add_argument("--role", help="Launch specific role interactively")
    parser.add_argument(
        "--list", action="store_true", help="List available agents and roles"
    )
    parser.add_argument(
        "--exec",
        nargs=2,
        metavar=("ROLE", "PROMPT"),
        help="Execute role non-interactively",
    )
    parser.add_argument(
        "--parallel",
        metavar="TASKS_JSON",
        help="Run tasks in parallel from JSON file or stdin (-)",
    )
    args = parser.parse_args()

    config = load_config()

    if args.list:
        print("=== Available Agents ===")
        for name, cfg in config["agents"].items():
            model = cfg.get("model", "default")
            reasoning = cfg.get("reasoning_effort", "medium")
            print(f"  {name}: {cfg['command']} -m {model} (reasoning: {reasoning})")
        print("\n=== Available Roles ===")
        for name, cfg in config["roles"].items():
            print(f"  {name}: uses {cfg['agent']}")
        return

    prompts = load_prompts(config)

    if args.parallel:
        if args.parallel == "-":
            tasks = json.load(sys.stdin)
        else:
            with open(args.parallel) as f:
                tasks = json.load(f)

        print(f"Running {len(tasks)} tasks in parallel...", file=sys.stderr)
        results = run_parallel_tasks(config, prompts, tasks)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if args.exec:
        role, prompt = args.exec
        result = run_single_task(config, prompts, role, prompt, task_id="exec")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.role:
        if args.role not in config["roles"]:
            print(f"Error: Unknown role '{args.role}'")
            print(f"Available: {', '.join(config['roles'].keys())}")
            return 1
        agent_name = config["roles"][args.role]["agent"]
        system_prompt = prompts[args.role]
        print(f"Launching {args.role} role (agent: {agent_name})...")
    else:
        agent_name = config["orchestrator"]["agent"]
        system_prompt = build_system_context(config, prompts)
        print(f"Launching orchestrator (agent: {agent_name})...")

    agent_config = config["agents"][agent_name]

    context_file = Path(__file__).parent / ".orchestrator_context.md"
    context_file.write_text(system_prompt)
    print(f"Context saved to: {context_file} ({len(system_prompt)} chars)")
    print(f"Model: {agent_config.get('model', 'default')}")

    cmd = [agent_config["command"]]
    if "model" in agent_config:
        if agent_config["command"] == "claude":
            cmd.extend(["--model", agent_config["model"]])
        elif agent_config["command"] == "codex":
            cmd.extend(["-m", agent_config["model"]])

    if agent_config["command"] == "claude":
        cmd.extend(
            ["--system-prompt", system_prompt[:10000], "--dangerously-skip-permissions"]
        )

    print(f"Running: {' '.join(cmd[:3])}...")
    subprocess.run(cmd, cwd=os.getcwd())


if __name__ == "__main__":
    main()

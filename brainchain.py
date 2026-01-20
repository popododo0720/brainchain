#!/usr/bin/env python3
"""
Brainchain Launcher - Opens orchestrator CLI with prompts injected.
Usage: python brainchain.py [--role <role_name>]

Examples:
  python brainchain.py              # Launch orchestrator (default)
  python brainchain.py --role planner  # Launch planner role directly
"""

import tomllib
import subprocess
import sys
import os
import argparse
from pathlib import Path


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
    context_parts.append("| Role | Agent | Model |")
    context_parts.append("|------|-------|-------|")
    for role_name, role_config in config["roles"].items():
        agent_name = role_config["agent"]
        model = config["agents"][agent_name].get("model", "default")
        context_parts.append(f"| {role_name} | {agent_name} | {model} |")

    context_parts.append("\n### Role Prompt Details\n")
    for role_name, role_config in config["roles"].items():
        agent_name = role_config["agent"]
        context_parts.append(f"\n#### {role_name} (uses {agent_name})\n")
        context_parts.append(f"```\n{prompts[role_name]}\n```\n")

    return "\n".join(context_parts)


def build_cli_command(agent_config, prompt=None):
    cmd = [agent_config["command"]]

    if "model" in agent_config:
        if agent_config["command"] == "claude":
            cmd.extend(["--model", agent_config["model"]])
        elif agent_config["command"] == "codex":
            cmd.extend(["-m", agent_config["model"]])

    if prompt:
        if agent_config["command"] == "claude":
            cmd.extend(["-p", prompt, "--print"])
        elif agent_config["command"] == "codex":
            cmd.extend(["exec", prompt, "--full-auto"])

    return cmd


def main():
    parser = argparse.ArgumentParser(description="Brainchain Launcher")
    parser.add_argument("--role", help="Launch specific role directly")
    parser.add_argument(
        "--list", action="store_true", help="List available agents and roles"
    )
    args = parser.parse_args()

    config = load_config()

    if args.list:
        print("=== Available Agents ===")
        for name, cfg in config["agents"].items():
            model = cfg.get("model", "default")
            print(f"  {name}: {cfg['command']} --model {model}")
        print("\n=== Available Roles ===")
        for name, cfg in config["roles"].items():
            print(f"  {name}: uses {cfg['agent']}")
        return

    prompts = load_prompts(config)

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

    cmd = build_cli_command(agent_config)

    if agent_config["command"] == "claude":
        cmd.extend(["--system-prompt", system_prompt[:10000]])

    print(f"Running: {' '.join(cmd[:3])}...")
    subprocess.run(cmd, cwd=os.getcwd())


if __name__ == "__main__":
    main()

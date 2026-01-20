# Brainchain

Multi-CLI AI Orchestrator with workflow automation.

## Install

```bash
./install.sh
```

## Usage

```bash
brainchain --list                    # List agents and roles
brainchain --exec planner "..."      # Run single task
brainchain --parallel tasks.json     # Run parallel tasks
brainchain --workflow "..."          # Run full workflow
```

## Workflow

```
Plan → Validate → Implement → Review → Fix
         ↑ (fail)              ↑ (fail)
         └──────────────────────┘
```

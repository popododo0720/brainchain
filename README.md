# Brainchain

Multi-CLI AI Orchestrator with workflow automation.

## Install

```bash
./install.sh
```

## Usage

```bash
brainchain                           # TUI chat interface
brainchain --list                    # List agents and roles
brainchain --exec <role> -p "..."    # Run single task
brainchain --parallel tasks.json     # Run parallel tasks
brainchain --workflow -p "..."       # Run full workflow
brainchain --sessions                # List sessions
brainchain --resume <session_id>     # Resume session
```

## Workflow

```
Plan → Validate → Implement → Review → Fix
         ↑ (fail)              ↑ (fail)
         └──────────────────────┘
```

## Configuration

Edit `~/.config/brainchain/config.toml`:

```toml
[orchestrator]
agent = "claude-opus"

[agents.claude-opus]
command = "claude"
model = "opus"
args = ["-p", "{prompt}", "--print"]
timeout = 300

[roles.planner]
agent = "claude-opus"
prompt_file = "prompts/planner.md"

[[workflow.steps]]
role = "planner"
output = "plan.json"
```

## Parallel Tasks

Create `tasks.json`:

```json
[
  {"id": "t1", "role": "implementer", "prompt": "Implement user model"},
  {"id": "t2", "role": "implementer", "prompt": "Implement auth routes"}
]
```

Run:

```bash
brainchain --parallel tasks.json
```

## Project Structure

```
cmd/chat/
├── main.go              # CLI entrypoint
├── tui.go               # Bubble Tea TUI
└── internal/
    ├── adapter/         # CLI adapters (claude, codex)
    ├── config/          # TOML configuration
    ├── executor/        # Task execution
    ├── session/         # SQLite session management
    └── workflow/        # Workflow engine
```

## Supported CLIs

- **claude** - Anthropic Claude Code
- **codex** - OpenAI Codex CLI

## License

MIT

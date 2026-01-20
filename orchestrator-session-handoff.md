# Orchestrator Project Session Handoff

## Goal
Build a custom AI orchestrator that:
1. Controls multiple CLI agents (Claude Code, Codex, OpenCode) 
2. Auto-distributes tasks with file ownership (no conflicts)
3. Follows spec-first, TDD workflow
4. Runs workers in parallel via subprocess

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    User Terminal                                │
│                                                                 │
│   User: "Build user auth system"                                │
│                         │                                       │
│                         ▼                                       │
│   ┌─────────────────────────────────────┐                      │
│   │         Orchestrator (Claude)       │                      │
│   │                                     │                      │
│   │  1. Plan (specs first)              │                      │
│   │  2. Dispatch tasks → Workers        │                      │
│   │  3. Collect results                 │                      │
│   │  4. Judge/validate                  │                      │
│   └──────────────┬──────────────────────┘                      │
│                  │ subprocess calls                            │
│   ┌──────────────┼──────────────────────┐                      │
│   │              ▼                      │                      │
│   │  ┌────────┐ ┌────────┐ ┌────────┐  │                      │
│   │  │Claude  │ │ Codex  │ │OpenCode│  │  (Background)        │
│   │  │Worker 1│ │Worker 2│ │Worker 3│  │                      │
│   │  │src/api/│ │src/db/ │ │src/ui/ │  │  (Exclusive files)   │
│   │  └────────┘ └────────┘ └────────┘  │                      │
│   └─────────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

## Key Decisions

### 1. Model Selection (User's subscriptions: Claude + GPT Plus)
- **Orchestrator**: `anthropic/claude-opus-4`
- **Planner**: `anthropic/claude-opus-4`  
- **Judge**: `anthropic/claude-opus-4`
- **Oracle** (advisor): `openai/gpt-5.2`
- **Workers**: Mix of Claude/GPT/Free models

### 2. Workflow Rules
- **Spec-first**: Must create `specs/api.md`, `specs/db.md`, `specs/architecture.md` before implementation
- **TDD**: Write tests before implementation
- **File ownership**: Each worker gets exclusive files (no overlap)
- **Linter**: Must pass before completion

### 3. CLI Tools to Orchestrate
```bash
# Claude Code
claude -p "task description" --print --allowedTools edit,write,bash

# Codex
codex -q "task description" --approval never --full-auto

# OpenCode  
opencode -m "task description" --no-interactive
```

## Implementation Plan

### Core Files to Create

```
orchestrator/
├── orchestrator.py          # Main orchestrator class
├── planner.py               # Plan generation (calls Claude)
├── dispatcher.py            # Task distribution to workers
├── judge.py                 # Result validation
├── workers/
│   ├── base.py              # Base worker interface
│   ├── claude_worker.py     # Claude Code CLI wrapper
│   ├── codex_worker.py      # Codex CLI wrapper
│   └── opencode_worker.py   # OpenCode CLI wrapper
├── utils/
│   ├── tmux_manager.py      # Optional: tmux visualization
│   └── file_lock.py         # File ownership tracking
├── config.yaml              # Model/agent configuration
└── run.py                   # Entry point
```

### Key Classes

```python
# orchestrator.py
class AutoOrchestrator:
    def __init__(self, project_dir: str)
    def plan(self, user_request: str) -> dict
    def create_specs(self, specs: list) -> None
    def dispatch_parallel(self, tasks: list) -> list
    def judge(self, results: list) -> dict
    def run(self, user_request: str) -> dict

# workers/base.py
class BaseWorker:
    def __init__(self, name: str, allowed_files: list)
    def execute(self, task: str) -> dict
    def get_status(self) -> str

# dispatcher.py
class TaskDispatcher:
    def __init__(self)
    def allocate_files(self, tasks: list) -> list  # Ensure no overlap
    def dispatch(self, task: dict) -> Future
    def dispatch_parallel(self, tasks: list) -> list
```

### Plan JSON Schema

```json
{
  "specs": [
    {"file": "specs/api.md", "description": "OpenAPI spec"},
    {"file": "specs/db.md", "description": "Database ERD"}
  ],
  "tasks": [
    {
      "id": 1,
      "agent": "claude",
      "task": "Implement JWT auth",
      "files": ["src/api/auth.ts", "tests/api/auth.test.ts"],
      "depends_on": []
    }
  ]
}
```

## Oh-My-OpenCode Integration (Alternative)

If using Oh-My-OpenCode 3.0 beta instead of custom orchestrator:

```jsonc
// ~/.config/opencode/oh-my-opencode.json
{
  "agents": {
    "Sisyphus": {
      "model": "anthropic/claude-opus-4",
      "promptAppend": "## Rules\n- Spec-first\n- TDD\n- File ownership per worker\n- Lint before complete"
    },
    "Prometheus (Planner)": {
      "model": "anthropic/claude-opus-4",
      "promptAppend": "## Planning\n- Create specs/api.md, specs/db.md first\n- Chunk tasks by directory\n- No file overlap"
    },
    "Momus": {
      "model": "anthropic/claude-opus-4",
      "promptAppend": "## Validation\n- Check specs exist\n- Check tests exist\n- Check lint passes\n- FAIL if missing"
    },
    "oracle": {
      "model": "openai/gpt-5.2"
    },
    "librarian": {
      "model": "opencode/glm-4.7-free"
    }
  }
}
```

## Next Steps

1. Create project structure
2. Implement `orchestrator.py` with subprocess calls
3. Implement workers for each CLI
4. Add file ownership tracking
5. Add tmux visualization (optional)
6. Test with simple request

## Commands to Start

```bash
# Create project
mkdir -p orchestrator/{workers,utils}
cd orchestrator

# Initialize
python -m venv venv
source venv/bin/activate
pip install libtmux pyyaml

# Then implement the files above
```

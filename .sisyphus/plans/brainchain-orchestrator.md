# Brainchain: Multi-CLI AI Orchestrator

## Context

### Original Request
여러 AI CLI(Claude Code, Codex)를 직접 subprocess로 호출하는 커스텀 오케스트레이터 구축. OpenCode는 프록시로 하위 모델이 되어서 사용 안 함. Opus 4.5 직접 사용.

### Interview Summary
**Key Discussions**:
- Sisyphus = Planner + Orchestrator (청크별 배타적 파일 분배)
- Claude Code → Claude Flow 또는 직접 호출
- Codex → 직접 subprocess 호출
- 설정파일(config.yaml) 기반 에이전트 정의
- Spec-first (api.md, db.md 먼저), TDD 워크플로우

**Cross-Validation 워크플로우** (사용자 추가 요청):
```
1. Claude: 계획 생성
2. Codex: 계획 검증 + 갭 찾기/수정
3. Claude: 단계별 실행 (사용자가 변경사항 주시)
4. Codex: 구현 검증
5. Claude: 문제 수정
```

**User Decisions**:
- 재시도 정책: 최대 2회 재시도
- Judge 실패 시: 해당 Worker에게 재작업 요청 (최대 2회)
- Judge 검증: 테스트, Spec 준수, 파일 범위, 린터, 빌드, 요구사항
- **각 역할별 커스텀 프롬프트**: config.yaml에 정의

### Metis Review
**Identified Gaps** (addressed):
- 재시도 정책 → 최대 2회로 확정
- Judge 실패 워크플로우 → Worker 재작업 요청으로 확정
- 파일 범위 강제 → Judge에서 사후 검증 (git diff 기반)
- Subprocess 정리 → SIGINT 핸들러로 cleanup

---

## Work Objectives

### Core Objective
여러 AI CLI를 병렬로 실행하고, 파일 충돌 없이 작업을 분배하며, 결과를 검증하는 오케스트레이터 구축

### Concrete Deliverables
```
brainchain/
├── config.toml              # 설정 (에이전트, 역할 매핑)
├── prompts/
│   ├── orchestrator.md      # 메인 오케스트레이터 (Sisyphus처럼)
│   ├── planner.md           # 계획 생성
│   ├── plan_validator.md    # 계획 검증
│   ├── implementer.md       # 구현
│   ├── code_reviewer.md     # 코드 리뷰
│   └── fixer.md             # 버그 수정
├── brainchain.py            # 셋업 스크립트 (config → CLI 실행)
└── specs/                   # 생성된 명세들 (런타임)
    ├── api.md
    └── db.md
```

**훨씬 간단해짐!**
- 별도 CLI 개발 불필요
- 워커/역할 클래스 불필요 → 프롬프트로 대체
- 워크플로우 엔진 불필요 → 오케스트레이터 프롬프트가 제어

### Definition of Done
- [ ] `python run.py "간단한 REST API 만들어줘"` 실행 시 전체 워크플로우 완료
- [ ] 최소 2개 Worker 병렬 실행 성공
- [ ] 파일 충돌 없이 결과 병합
- [ ] Judge 검증 통과

### Must Have
- Subprocess 기반 CLI 호출 (claude -p, codex -q)
- 파일 소유권 기반 청킹 (겹침 없음)
- 최대 2회 재시도 로직
- Judge: 테스트 + 빌드 검증
- config.yaml 기반 에이전트 설정

### Must NOT Have (Guardrails)
- tmux 시각화 (Phase 2로 분리)
- 공통 저장소/메모리 공유 (Phase 2로 분리)
- 린터 커스텀 룰 세팅 (Phase 2로 분리)
- 10개 이상 Python 파일
- 웹 UI / REST API
- BaseWorker 외 추가 추상화 레이어

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: NO (새 프로젝트)
- **User wants tests**: YES (TDD)
- **Framework**: pytest

### Test Setup Task
- [ ] 0. pytest 설치 및 설정
  - Install: `pip install pytest`
  - Config: `pytest.ini` 생성
  - Verify: `pytest --version`

### TDD Workflow
각 TODO는 RED-GREEN-REFACTOR:
1. **RED**: 실패하는 테스트 먼저 작성
2. **GREEN**: 테스트 통과하는 최소 구현
3. **REFACTOR**: 코드 정리 (테스트 유지)

---

## Task Flow (간소화됨!)

```
Phase 0: CLI 검증 (claude, codex 설치 확인)
    ↓
Phase 1: config.toml + brainchain.py (셋업 스크립트)
    ↓
Phase 2: 오케스트레이터 프롬프트 작성
    ↓
Phase 3: 역할별 프롬프트 작성 [병렬 가능]
    ↓
Phase 4: E2E 테스트
```

### Cross-Validation 워크플로우 상세

```
┌─────────────────────────────────────────────────────────────────┐
│  User Request: "Build user auth system"                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. PLANNER (Claude)                                            │
│     - Create specs (api.md, db.md)                              │
│     - Generate plan.json with tasks + file assignments          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. PLAN VALIDATOR (Codex)                                      │
│     - Review plan for gaps                                      │
│     - Check file conflicts                                      │
│     - APPROVED → continue / NEEDS_REVISION → back to planner    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. IMPLEMENTER (Claude) - Per Task Loop                        │
│     - Execute task (TDD: test first)                            │
│     - User watches changes in real-time                         │
│                              │                                  │
│                              ▼                                  │
│  4. CODE REVIEWER (Codex)                                       │
│     - Verify implementation                                     │
│     - PASSED → next task / FAILED → to fixer                    │
│                              │                                  │
│                              ▼                                  │
│  5. FIXER (Claude) - if needed                                  │
│     - Fix reported issues                                       │
│     - Back to code reviewer                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DONE: All tasks completed and validated                        │
└─────────────────────────────────────────────────────────────────┘
```

## Parallelization

| Group | Tasks | Reason |
|-------|-------|--------|
| A | 3 (role prompts) | 각 프롬프트 독립적 작성 가능 |

| Task | Depends On | Reason |
|------|------------|--------|
| 1 | 0 | CLI 확인 후 config 작성 |
| 2 | 1 | config 구조 확정 후 오케스트레이터 프롬프트 |
| 3 | 2 | 오케스트레이터가 역할 프롬프트 참조 |
| 4 | 3 | 모든 프롬프트 완성 후 E2E |

---

## TODOs

- [ ] 0. CLI 환경 검증 및 프로젝트 셋업

  **What to do**:
  - `claude --version`, `codex --version` 실행 확인
  - 프로젝트 디렉토리 구조 생성: `brainchain/`, `brainchain/prompts/`
  - Python 3.11+ 확인 (tomllib 내장)

  **Must NOT do**:
  - 불필요한 의존성 설치

  **Parallelizable**: NO (첫 번째 태스크)

  **Acceptance Criteria**:
  - [ ] `claude --version` → 버전 출력
  - [ ] `codex --version` → 버전 출력
  - [ ] `python --version` → 3.11+
  - [ ] `brainchain/prompts/` 디렉토리 생성 완료

  **Commit**: YES
  - Message: `chore: initial project setup`
  - Files: `brainchain/`, `brainchain/prompts/`

---

- [ ] 1. config.toml + brainchain.py 작성

  **What to do**:
  - `config.toml` 작성 (에이전트 정의, 역할 매핑)
  - `brainchain.py` 작성: config 읽고 → CLI 실행 + 프롬프트 주입
  - 사용법: `python brainchain.py` → 오케스트레이터 CLI 열림

  **Must NOT do**:
  - 복잡한 로직 (단순 config → CLI 실행만)

  **Parallelizable**: NO (프롬프트가 의존)

  **References**:
  - Python tomllib: https://docs.python.org/3/library/tomllib.html
  - Claude CLI: `claude -p "prompt" --allowedTools Edit,Write,Bash`
  - Codex CLI: `codex -q "prompt" --approval never`

  **config.toml 예시**:
  ```toml
  # === 오케스트레이터 설정 ===
  [orchestrator]
  agent = "claude-opus"           # 메인 CLI로 열릴 에이전트
  prompt_file = "prompts/orchestrator.md"

  # === 에이전트 정의 (CLI 방식) ===
  # 모델별로 에이전트를 정의하면 역할별 모델 선택 가능!

  [agents.claude-opus]
  type = "cli"
  command = "claude"
  model = "opus"                  # --model opus (비싼 작업용)
  args = ["-p", "{prompt}", "--print", "--allowedTools", "Edit,Write,Bash"]
  timeout = 300

  [agents.claude-sonnet]
  type = "cli"
  command = "claude"
  model = "sonnet"                # --model sonnet (균형)
  args = ["-p", "{prompt}", "--print", "--allowedTools", "Edit,Write,Bash"]
  timeout = 300

  [agents.claude-haiku]
  type = "cli"
  command = "claude"
  model = "haiku"                 # --model haiku (저렴한 작업용)
  args = ["-p", "{prompt}", "--print", "--allowedTools", "Edit,Write,Bash"]
  timeout = 120

  [agents.codex]
  type = "cli"
  command = "codex"
  model = "codex"                 # -m codex
  args = ["exec", "{prompt}", "--full-auto"]
  timeout = 300

  [agents.codex-gpt4o]
  type = "cli"
  command = "codex"
  model = "gpt-4o"                # -m gpt-4o
  args = ["exec", "{prompt}", "--full-auto"]
  timeout = 300

  # === 역할별 설정 (에이전트+모델 조합 선택!) ===
  [roles.planner]
  agent = "claude-opus"           # 계획은 비싼 모델 (복잡한 작업)
  prompt_file = "prompts/planner.md"

  [roles.plan_validator]
  agent = "codex"                 # 검증은 Codex
  prompt_file = "prompts/plan_validator.md"

  [roles.implementer]
  agent = "claude-sonnet"         # 구현은 중간 모델
  prompt_file = "prompts/implementer.md"

  [roles.code_reviewer]
  agent = "claude-haiku"          # 리뷰는 저렴한 모델로도 OK
  prompt_file = "prompts/code_reviewer.md"

  [roles.fixer]
  agent = "claude-sonnet"         # 수정은 중간 모델
  prompt_file = "prompts/fixer.md"

  # === 워크플로우 ===
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

  # === 기타 설정 ===
  [retry_policy]
  max_retries = 2
  retry_delay = 5

  [judge]
  test_command = "pytest"
  build_command = "python -m py_compile"
  ```

  ---

  ### 프롬프트 파일 예시 (영어, oh-my-opencode/CrewAI/LangChain 패턴 참조)

  **prompts/orchestrator.md**:
  ```markdown
  # Brainchain Orchestrator

  You are the orchestrator of a multi-agent coding system. Your role is to coordinate
  specialized agents to complete complex development tasks efficiently.

  ## Core Identity

  - **Operating Mode**: Coordinator, not implementer. You delegate work, don't do it yourself.
  - **Philosophy**: Spec-first, TDD, file ownership. No conflicts, no chaos.
  - **Quality Bar**: Code should be indistinguishable from a senior engineer's work.

  ## Workflow (Cross-Validation Pattern)

  ```
  1. PLAN    → Generate specs + task breakdown (Planner)
  2. VALIDATE → Review plan for gaps (Validator) → Loop back if issues
  3. IMPLEMENT → Execute tasks one by one (Implementer)
  4. REVIEW  → Verify implementation (Reviewer) → Loop to Fixer if issues
  5. FIX     → Address review feedback (Fixer) → Back to Review
  ```

  ## How to Call Other Agents

  Use subprocess to invoke CLI agents:

  ```bash
  # Claude agent
  claude -p "<ROLE_PROMPT>\n\n<YOUR_TASK>" --print --allowedTools Edit,Write,Bash

  # Codex agent  
  codex -q "<ROLE_PROMPT>\n\n<YOUR_TASK>" --approval never --full-auto
  ```

  ## Delegation Prompt Structure (MANDATORY)

  When delegating to any role, your prompt MUST include:

  | Section | Description |
  |---------|-------------|
  | **TASK** | Atomic, specific goal (one action per delegation) |
  | **CONTEXT** | Relevant specs, file paths, existing patterns |
  | **MUST DO** | Exhaustive requirements - leave NOTHING implicit |
  | **MUST NOT DO** | Forbidden actions - anticipate and block scope creep |
  | **OUTPUT FORMAT** | Expected response structure (JSON schema if applicable) |

  ## File Ownership Rules (CRITICAL)

  - Each task has EXCLUSIVE files. No overlap between concurrent tasks.
  - Before dispatching: verify no file conflicts with `git status`
  - After completion: verify only assigned files changed with `git diff --name-only`
  - Violation = REJECT and reassign

  ## Role → Agent Mapping

  Read from config.toml. Example:
  - planner: claude
  - plan_validator: codex
  - implementer: claude
  - code_reviewer: codex
  - fixer: claude

  These can be swapped by changing config. Your logic should be agent-agnostic.

  ## Hard Blocks (NEVER violate)

  | Constraint | No Exceptions |
  |------------|---------------|
  | Implement without plan | Never |
  | Skip validation step | Never |
  | Overlapping file assignments | Never |
  | Ignore reviewer feedback | Never |
  | Commit without explicit request | Never |
  ```

  **prompts/planner.md**:
  ```markdown
  # Planner Role

  You are a meticulous technical planner. Your job is to transform user requests
  into actionable, unambiguous work plans.

  ## Operating Principles

  - **Spec-first**: Create API and DB specs BEFORE any implementation tasks
  - **Atomic tasks**: Each task should be completable in one focused session
  - **File ownership**: Every file belongs to exactly ONE task. No overlaps.
  - **TDD**: Test files are part of the task scope, not afterthoughts

  ## Output Format

  Return a JSON object with this exact structure:

  ```json
  {
    "specs": [
      {
        "file": "specs/api.md",
        "description": "REST API specification",
        "content": "## Endpoints\n\n### POST /users\n..."
      },
      {
        "file": "specs/db.md", 
        "description": "Database schema",
        "content": "## Tables\n\n### users\n..."
      }
    ],
    "tasks": [
      {
        "id": 1,
        "description": "Implement user model and migrations",
        "files": ["src/models/user.py", "tests/test_user_model.py"],
        "depends_on": [],
        "acceptance_criteria": [
          "User model has id, email, password_hash fields",
          "pytest tests/test_user_model.py passes"
        ]
      }
    ]
  }
  ```

  ## Validation Checklist (self-verify before output)

  - [ ] Every task has exclusive file ownership (no file appears in multiple tasks)
  - [ ] Tasks with dependencies are correctly ordered
  - [ ] Acceptance criteria are concrete and testable
  - [ ] Test files included in relevant task's file list
  - [ ] Specs reference actual implementation file paths

  ## MUST NOT

  - Create tasks with overlapping files
  - Leave acceptance criteria vague ("it should work")
  - Skip spec generation for non-trivial features
  - Include implementation details in specs (specs define WHAT, not HOW)
  ```

  **prompts/plan_validator.md**:
  ```markdown
  # Plan Validator Role

  You are a critical reviewer of work plans. Your job is to find gaps, ambiguities,
  and potential issues BEFORE implementation begins.

  ## Review Checklist

  ### 1. File Ownership Conflicts
  - Scan all tasks for overlapping files
  - Flag: "File X assigned to both Task N and Task M"

  ### 2. Dependency Correctness
  - Verify depends_on references exist
  - Check for circular dependencies
  - Flag: "Task N depends on Task M, but M depends on N"

  ### 3. Acceptance Criteria Quality
  - Must be concrete and testable
  - Flag: Vague criteria like "works correctly", "handles errors"
  - Suggest: Specific command to run + expected output

  ### 4. Spec Completeness
  - API spec should cover all endpoints mentioned in tasks
  - DB spec should cover all models referenced
  - Flag: "Task references User model but specs/db.md missing users table"

  ### 5. Missing Tasks
  - Identify work implied but not explicitly tasked
  - Flag: "API endpoint /users mentioned but no task creates it"

  ## Output Format

  ```json
  {
    "verdict": "APPROVED" | "NEEDS_REVISION",
    "issues": [
      {
        "severity": "critical" | "warning",
        "location": "task.3.files",
        "issue": "File src/auth.py also assigned to task.1",
        "suggestion": "Move auth.py to task.1 or split into separate files"
      }
    ],
    "summary": "Found 2 critical issues that must be fixed before proceeding."
  }
  ```

  ## Decision Rules

  - **APPROVED**: Zero critical issues, warnings are acceptable
  - **NEEDS_REVISION**: Any critical issue present
  ```

  **prompts/implementer.md**:
  ```markdown
  # Implementer Role

  You are a focused implementer. Your job is to execute ONE task at a time,
  following TDD principles and staying strictly within scope.

  ## Operating Principles

  - **TDD**: Write failing test FIRST, then implement to make it pass
  - **Scope discipline**: Only touch files assigned to your task
  - **Pattern following**: Match existing codebase conventions
  - **Minimal changes**: Smallest code that satisfies acceptance criteria

  ## Workflow

  1. Read the task description and acceptance criteria
  2. Write failing tests for each acceptance criterion
  3. Implement minimal code to pass tests
  4. Refactor if needed (tests must stay green)
  5. Report completion with file changes

  ## Output Format

  ```json
  {
    "status": "completed" | "blocked",
    "files_changed": ["src/auth.py", "tests/test_auth.py"],
    "tests_added": ["test_login_success", "test_login_invalid_password"],
    "notes": "Optional notes about implementation decisions",
    "blockers": ["Only if status=blocked: what's preventing completion"]
  }
  ```

  ## MUST DO

  - Write test before implementation (RED → GREEN → REFACTOR)
  - Run tests after implementation to verify
  - Follow existing code style and patterns
  - Report all files actually modified

  ## MUST NOT

  - Modify files outside assigned scope
  - Skip writing tests
  - Add features not in acceptance criteria
  - Refactor unrelated code "while you're at it"
  - Use type suppressions (as any, @ts-ignore)
  ```

  **prompts/code_reviewer.md**:
  ```markdown
  # Code Reviewer Role

  You are a strict code reviewer. Your job is to verify implementations
  meet specifications and quality standards.

  ## Review Checklist

  ### 1. Spec Compliance
  - Does implementation match API/DB specs?
  - Are all acceptance criteria satisfied?

  ### 2. Test Coverage
  - Do tests cover the acceptance criteria?
  - Are edge cases tested?
  - Do all tests pass?

  ### 3. Scope Compliance
  - Only assigned files modified?
  - No unrelated changes snuck in?

  ### 4. Code Quality
  - Follows existing patterns?
  - No obvious bugs or security issues?
  - No type suppressions or empty catch blocks?

  ## Output Format

  ```json
  {
    "verdict": "PASSED" | "FAILED",
    "checks": {
      "spec_compliance": true,
      "tests_pass": true,
      "scope_compliance": true,
      "code_quality": true
    },
    "issues": [
      {
        "file": "src/auth.py",
        "line": 42,
        "severity": "critical" | "warning",
        "issue": "Missing input validation for email",
        "suggestion": "Add email format check before database query"
      }
    ]
  }
  ```

  ## Decision Rules

  - **PASSED**: All checks pass, no critical issues
  - **FAILED**: Any critical issue OR tests fail OR scope violation
  ```

  **prompts/fixer.md**:
  ```markdown
  # Fixer Role

  You are a focused bug fixer. Your job is to address ONLY the issues
  identified by the code reviewer.

  ## Operating Principles

  - **Surgical fixes**: Change only what's needed to fix reported issues
  - **No scope creep**: Do not "improve" unrelated code
  - **Test verification**: Run tests after each fix

  ## Input

  You receive:
  1. The original task description
  2. The reviewer's issue list

  ## Workflow

  1. For each issue in the list:
     a. Locate the file and line
     b. Apply the minimal fix
     c. Run tests to verify fix doesn't break anything
  2. Report completion

  ## Output Format

  ```json
  {
    "status": "fixed" | "partial" | "blocked",
    "fixes_applied": [
      {
        "issue": "Missing input validation for email",
        "file": "src/auth.py",
        "fix": "Added email format validation using regex"
      }
    ],
    "remaining_issues": [],
    "tests_pass": true
  }
  ```

  ## MUST DO

  - Address every issue in the reviewer's list
  - Run tests after fixes
  - Report exactly what was changed

  ## MUST NOT

  - Fix things not in the issue list
  - Refactor code "to make it better"
  - Add new features
  - Ignore any reported issue
  ```

  **구현 패턴**:
  ```python
  # brainchain.py
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
      """Load orchestrator and role prompts."""
      prompts = {}
      base_path = Path(__file__).parent
      
      # Load orchestrator prompt
      orch_prompt_path = base_path / config["orchestrator"]["prompt_file"]
      prompts["orchestrator"] = orch_prompt_path.read_text()
      
      # Load role prompts
      for role_name, role_config in config["roles"].items():
          prompt_path = base_path / role_config["prompt_file"]
          prompts[role_name] = prompt_path.read_text()
      
      return prompts

  def build_system_context(config, prompts):
      """Build the full system context for the orchestrator."""
      context_parts = [
          prompts["orchestrator"],
          "\n---\n## Available Role Prompts\n"
      ]
      
      # Add role → agent mapping summary
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
      """Build CLI command with model and args."""
      cmd = [agent_config["command"]]
      
      # Add model flag
      if "model" in agent_config:
          if agent_config["command"] == "claude":
              cmd.extend(["--model", agent_config["model"]])
          elif agent_config["command"] == "codex":
              cmd.extend(["-m", agent_config["model"]])
      
      # Add prompt if provided (non-interactive mode)
      if prompt:
          if agent_config["command"] == "claude":
              cmd.extend(["-p", prompt, "--print"])
          elif agent_config["command"] == "codex":
              cmd.extend(["exec", prompt, "--full-auto"])
      
      return cmd

  def main():
      parser = argparse.ArgumentParser(description="Brainchain Launcher")
      parser.add_argument("--role", help="Launch specific role directly")
      parser.add_argument("--list", action="store_true", help="List available agents and roles")
      args = parser.parse_args()
      
      config = load_config()
      prompts = load_prompts(config)
      
      # List mode
      if args.list:
          print("=== Available Agents ===")
          for name, cfg in config["agents"].items():
              model = cfg.get("model", "default")
              print(f"  {name}: {cfg['command']} --model {model}")
          print("\n=== Available Roles ===")
          for name, cfg in config["roles"].items():
              print(f"  {name}: uses {cfg['agent']}")
          return
      
      # Determine which agent to launch
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
      
      # Save context to temp file
      context_file = Path(__file__).parent / ".orchestrator_context.md"
      context_file.write_text(system_prompt)
      print(f"Context saved to: {context_file} ({len(system_prompt)} chars)")
      print(f"Model: {agent_config.get('model', 'default')}")
      
      # Build and run command
      cmd = build_cli_command(agent_config)
      
      # For interactive mode, add system prompt flag if supported
      if agent_config["command"] == "claude":
          cmd.extend(["--system-prompt", system_prompt[:10000]])  # truncate if too long
      
      print(f"Running: {' '.join(cmd[:3])}...")
      subprocess.run(cmd, cwd=os.getcwd())

  if __name__ == "__main__":
      main()
  ```

  **Acceptance Criteria**:
  - [ ] `python brainchain.py` 실행 → "Launching claude as orchestrator..." 메시지 출력
  - [ ] `.orchestrator_context.md` 파일 생성됨 (context 저장)
  - [ ] CLI가 열림 (subprocess 성공)
  - [ ] context 파일에 orchestrator.md 내용 포함 확인: `grep "Cross-Validation Pattern" .orchestrator_context.md`

  **Commit**: YES
  - Message: `feat: add config.toml and brainchain.py launcher`
  - Files: `brainchain/config.toml`, `brainchain/brainchain.py`

---

- [ ] 2. 오케스트레이터 프롬프트 작성 (orchestrator.md)

  **What to do**:
  - `prompts/orchestrator.md`: 메인 오케스트레이터 프롬프트
  - oh-my-opencode의 Sisyphus처럼 다른 에이전트 호출 지시
  - Cross-validation 워크플로우 정의
  - 역할별 프롬프트 참조 방법 포함

  **Must NOT do**:
  - 하드코딩된 에이전트 이름 (config에서 읽도록)

  **Parallelizable**: NO (역할 프롬프트가 의존)

  **프롬프트 구조**:
  ```markdown
  # Brainchain Orchestrator

  You are the orchestrator. Your job is to coordinate multiple AI agents
  to complete complex tasks.

  ## Workflow
  1. **Planning**: Call {planner_agent} with planner prompt
  2. **Validation**: Call {validator_agent} to review plan
  3. **Implementation**: For each task, call {implementer_agent}
  4. **Review**: Call {reviewer_agent} to verify
  5. **Fix**: If issues, call {fixer_agent}

  ## How to Call Other Agents
  Use subprocess or SDK to invoke:
  - Claude: `claude -p "<prompt>" --print`
  - Codex: `codex -q "<prompt>" --approval never`

  ## File Ownership Rules
  - Each task has exclusive files
  - NEVER modify files outside your assigned scope
  - Verify with `git diff --name-only`

  ## Current Roles
  {dynamically_loaded_from_config}
  ```

  **Acceptance Criteria**:
  - [ ] `prompts/orchestrator.md` 파일 존재
  - [ ] 파일에 5단계 워크플로우 포함: `grep -c "PLAN\|VALIDATE\|IMPLEMENT\|REVIEW\|FIX" prompts/orchestrator.md` → 5 이상
  - [ ] CLI 호출 예시 포함: `grep "claude -p" prompts/orchestrator.md` → 결과 있음
  - [ ] Delegation Prompt Structure 섹션 포함: `grep "MUST DO\|MUST NOT DO" prompts/orchestrator.md`
  - [ ] File Ownership Rules 섹션 포함: `grep "EXCLUSIVE files" prompts/orchestrator.md`

  **Commit**: YES
  - Message: `feat: add orchestrator prompt`
  - Files: `brainchain/prompts/orchestrator.md`

---

- [ ] 3. 역할별 프롬프트 작성

  **What to do**:
  - `prompts/planner.md`: 계획 생성 프롬프트
  - `prompts/plan_validator.md`: 계획 검증 프롬프트
  - `prompts/implementer.md`: 구현 프롬프트
  - `prompts/code_reviewer.md`: 코드 리뷰 프롬프트
  - `prompts/fixer.md`: 버그 수정 프롬프트

  **Must NOT do**:
  - 역할 간 중복 내용
  - 하드코딩된 파일 경로

  **Parallelizable**: YES (각 프롬프트 독립적)

  **각 프롬프트 핵심 내용**:

  **planner.md**:
  - specs (api.md, db.md) 먼저 생성
  - 태스크 청킹 (파일 겹침 없이)
  - JSON 출력 형식

  **plan_validator.md**:
  - 갭 찾기, 파일 충돌 확인
  - APPROVED / NEEDS_REVISION 출력

  **implementer.md**:
  - TDD (테스트 먼저)
  - 할당된 파일만 수정
  - 완료 보고

  **code_reviewer.md**:
  - spec 준수 확인
  - 테스트 커버리지 확인
  - PASSED / FAILED + issues 출력

  **fixer.md**:
  - 리뷰 이슈만 수정
  - 불필요한 리팩토링 금지

  **Acceptance Criteria**:
  - [ ] `ls prompts/*.md | wc -l` → 6 (orchestrator + 5 roles)
  - [ ] 각 프롬프트에 OUTPUT FORMAT 섹션 있음: `grep -l "OUTPUT FORMAT\|Output Format" prompts/*.md | wc -l` → 5 이상
  - [ ] 각 프롬프트에 MUST NOT 섹션 있음: `grep -l "MUST NOT" prompts/*.md | wc -l` → 5 이상
  - [ ] planner.md에 JSON schema 있음: `grep "tasks.*files.*depends_on" prompts/planner.md`

  **Commit**: YES
  - Message: `feat: add role prompts (planner, validator, implementer, reviewer, fixer)`
  - Files: `brainchain/prompts/*.md`

---

- [ ] 4. E2E 테스트

  **What to do**:
  - `python brainchain.py` 실행
  - 간단한 요청 테스트: "Create a Python function that adds two numbers"
  - 전체 워크플로우 검증: Plan → Validate → Implement → Review

  **Must NOT do**:
  - 복잡한 시나리오 (단순한 것 하나만)

  **Parallelizable**: NO (최종 검증)

  **Acceptance Criteria**:
  - [ ] `python brainchain.py` → CLI 열림
  - [ ] 요청 입력 → Planner가 계획 생성
  - [ ] Validator가 계획 검증
  - [ ] Implementer가 구현
  - [ ] Reviewer가 검증
  - [ ] 최종 결과물 생성 확인

  **Commit**: YES
  - Message: `test: add E2E test scenario`
  - Files: `brainchain/test_e2e.md` (테스트 시나리오 문서)

---

## Commit Strategy (간소화됨!)

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 0 | `chore: initial setup` | brainchain/ | CLI version check |
| 1 | `feat: add config.toml and launcher` | config.toml, brainchain.py | manual run |
| 2 | `feat: add orchestrator prompt` | prompts/orchestrator.md | manual review |
| 3 | `feat: add role prompts` | prompts/*.md | manual review |
| 4 | `test: E2E verification` | test_e2e.md | manual run |

---

## Success Criteria

### Verification Commands
```bash
# 실행
cd brainchain
python brainchain.py

# CLI 열리면 요청 입력
> "Create a simple REST API with user authentication"

# 결과 확인
ls specs/  # api.md, db.md 존재
```

### Final Checklist
- [ ] `python brainchain.py` → Claude/Codex CLI 열림
- [ ] 오케스트레이터가 역할별로 다른 에이전트 호출
- [ ] Cross-validation 워크플로우 동작 (Plan → Validate → Implement → Review)
- [ ] 파일 소유권 규칙 준수

---

## Phase 2 (나중에)
- tmux 시각화
- 공통 저장소 (SQLite or JSON)
- 린터 커스텀 룰
- Spec 준수 검증 (LLM 기반)
- 요구사항 충족 검증 (LLM 기반)
- Claude Flow 통합 (단순 CLI → 고급 오케스트레이션)

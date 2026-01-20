# Brainchain E2E Test Documentation

## Objective

Verify the complete brainchain orchestration workflow from initial request through final implementation, validation, and review. This document describes how to manually test the multi-agent coordination system.

## System Overview

Brainchain is a multi-CLI orchestrator that coordinates specialized agents (Claude and Codex) to complete development tasks through a structured workflow:

```
User Request
    ↓
[PLAN] Planner generates specs + task breakdown
    ↓
[VALIDATE] Plan Validator reviews plan for gaps
    ↓
[IMPLEMENT] Implementer executes tasks
    ↓
[REVIEW] Code Reviewer verifies implementation
    ↓
[FIX] Fixer addresses issues (if needed)
    ↓
Final Output
```

## Prerequisites

- Python 3.11+
- Claude CLI installed and configured (`claude --version`)
- Codex CLI installed and configured (`codex --version`)
- Git configured for the project
- All brainchain components in place:
  - `brainchain.py` (launcher)
  - `config.toml` (agent and role configuration)
  - `prompts/` directory with 6 prompt files:
    - `orchestrator.md`
    - `planner.md`
    - `plan_validator.md`
    - `implementer.md`
    - `code_reviewer.md`
    - `fixer.md`

## Quick Verification (Non-Interactive)

Before running the full E2E test, verify the launcher works:

```bash
# List available agents and roles
python3 brainchain.py --list

# Expected output:
# === Available Agents ===
#   claude-opus: claude --model opus
#   claude-sonnet: claude --model sonnet
#   claude-haiku: claude --model haiku
#   codex: codex --model codex
#   codex-gpt4o: codex --model gpt-4o
#   codex-gpt5: codex --model gpt-5.2
#
# === Available Roles ===
#   planner: uses claude-opus
#   plan_validator: uses codex-gpt5
#   implementer: uses claude-opus
#   code_reviewer: uses codex-gpt5
#   fixer: uses claude-opus
```

This confirms:
- ✅ Config file loads correctly
- ✅ All agents are defined
- ✅ All roles are mapped to agents
- ✅ Launcher is functional

## Full E2E Test Scenario

### Test Request

```
Create a Python function that adds two numbers and returns the result.
The function should:
- Accept two parameters (a, b)
- Return their sum
- Include docstring
- Include type hints
- Include unit tests
```

### Step 1: Launch Orchestrator

```bash
python3 brainchain.py
```

**Expected behavior:**
- Launcher prints: `Launching orchestrator (agent: claude-opus)...`
- Launcher prints: `Context saved to: .orchestrator_context.md (XXXX chars)`
- Claude CLI opens with orchestrator prompt injected
- Orchestrator prompt includes:
  - Core identity and operating mode
  - Workflow description (PLAN → VALIDATE → IMPLEMENT → REVIEW → FIX)
  - Delegation prompt structure
  - File ownership rules
  - Role → Agent mapping table
  - All 5 role prompts

**Verification:**
- [ ] Claude CLI window opens
- [ ] `.orchestrator_context.md` file created (9-10KB)
- [ ] Context file contains orchestrator prompt
- [ ] Context file contains role mappings table
- [ ] Context file contains all 5 role prompts

### Step 2: Submit Test Request to Orchestrator

In the Claude CLI, paste the test request:

```
Create a Python function that adds two numbers and returns the result.
The function should:
- Accept two parameters (a, b)
- Return their sum
- Include docstring
- Include type hints
- Include unit tests
```

**Expected behavior:**
- Orchestrator reads the request
- Orchestrator recognizes it needs to follow the workflow
- Orchestrator decides to call the Planner role first

### Step 3: Planning Stage

**What happens:**
- Orchestrator calls: `claude -p "<PLANNER_PROMPT>\n\n<REQUEST>" --print --allowedTools Edit,Write,Bash`
- Planner agent receives the request with planner role prompt
- Planner generates a detailed plan including:
  - Task breakdown (e.g., "Create add_numbers function", "Write unit tests")
  - File structure (e.g., `add_numbers.py`, `test_add_numbers.py`)
  - Implementation details
  - Success criteria

**Verification checklist:**
- [ ] Planner agent launches successfully
- [ ] Planner generates structured plan (JSON or markdown)
- [ ] Plan includes task breakdown
- [ ] Plan specifies files to create/modify
- [ ] Plan includes success criteria

**Expected output example:**
```json
{
  "tasks": [
    {
      "id": 1,
      "title": "Create add_numbers function",
      "description": "Implement function with type hints and docstring",
      "files": ["add_numbers.py"]
    },
    {
      "id": 2,
      "title": "Write unit tests",
      "description": "Create comprehensive test suite",
      "files": ["test_add_numbers.py"]
    }
  ],
  "success_criteria": [
    "Function accepts two parameters",
    "Function returns correct sum",
    "All tests pass"
  ]
}
```

### Step 4: Validation Stage

**What happens:**
- Orchestrator calls: `codex -q "<VALIDATOR_PROMPT>\n\n<PLAN>" --approval never --full-auto`
- Plan Validator (Codex GPT-5.2) reviews the plan
- Validator checks for:
  - Completeness (all requirements covered)
  - Feasibility (tasks are achievable)
  - Clarity (no ambiguous requirements)
  - Gaps (missing edge cases or tests)

**Verification checklist:**
- [ ] Plan Validator agent launches
- [ ] Validator reviews plan thoroughly
- [ ] Validator provides approval or feedback
- [ ] If issues found, orchestrator loops back to Planner
- [ ] If approved, orchestrator proceeds to Implementation

**Expected outcomes:**
- **Approved:** "Plan is complete and feasible. Proceeding to implementation."
- **Rejected:** "Plan needs revision: missing error handling for invalid inputs"

### Step 5: Implementation Stage

**What happens:**
- Orchestrator calls: `claude -p "<IMPLEMENTER_PROMPT>\n\n<PLAN>" --print --allowedTools Edit,Write,Bash`
- Implementer agent receives the approved plan
- Implementer creates/modifies files according to plan
- Implementer executes tasks sequentially

**Verification checklist:**
- [ ] Implementer agent launches
- [ ] Implementer creates `add_numbers.py` with:
  - Function definition with type hints
  - Comprehensive docstring
  - Correct implementation
- [ ] Implementer creates `test_add_numbers.py` with:
  - Unit tests for normal cases
  - Edge case tests (zero, negative numbers)
  - Test execution confirmation
- [ ] All files created in correct location
- [ ] Code follows Python best practices

**Expected output:**
```python
# add_numbers.py
def add_numbers(a: int, b: int) -> int:
    """
    Add two numbers and return the result.
    
    Args:
        a: First number
        b: Second number
    
    Returns:
        The sum of a and b
    """
    return a + b
```

### Step 6: Review Stage

**What happens:**
- Orchestrator calls: `codex -q "<REVIEWER_PROMPT>\n\n<IMPLEMENTATION>" --approval never --full-auto`
- Code Reviewer (Codex GPT-5.2) examines implementation
- Reviewer checks:
  - Code quality and style
  - Test coverage
  - Documentation completeness
  - Adherence to requirements
  - Potential bugs or issues

**Verification checklist:**
- [ ] Code Reviewer agent launches
- [ ] Reviewer analyzes implementation
- [ ] Reviewer provides detailed feedback
- [ ] If issues found, orchestrator calls Fixer
- [ ] If approved, workflow completes successfully

**Expected outcomes:**
- **Approved:** "Implementation meets all requirements. Tests pass. Code quality is excellent."
- **Issues found:** "Missing edge case: what if inputs are floats? Current implementation assumes integers."

### Step 7: Fix Stage (If Needed)

**What happens (only if Reviewer found issues):**
- Orchestrator calls: `claude -p "<FIXER_PROMPT>\n\n<FEEDBACK>" --print --allowedTools Edit,Write,Bash`
- Fixer agent receives reviewer feedback
- Fixer modifies code to address issues
- After fixes, orchestrator loops back to Review stage

**Verification checklist:**
- [ ] Fixer agent launches (if needed)
- [ ] Fixer addresses all reviewer feedback
- [ ] Fixer updates implementation
- [ ] Fixer runs tests to verify fixes
- [ ] Orchestrator calls Reviewer again
- [ ] Reviewer approves fixed implementation

### Step 8: Final Output

**Expected result:**
- ✅ `add_numbers.py` created with correct implementation
- ✅ `test_add_numbers.py` created with comprehensive tests
- ✅ All tests passing
- ✅ Code reviewed and approved
- ✅ Documentation complete
- ✅ All requirements met

## Verification Checklist

Complete this checklist to confirm successful E2E test:

### Launcher Verification
- [ ] `python3 brainchain.py --list` runs without errors
- [ ] Output shows all 6 agents
- [ ] Output shows all 5 roles
- [ ] Role → Agent mappings are correct

### Context File Verification
- [ ] `.orchestrator_context.md` created after running launcher
- [ ] File size is 9-10KB (contains full context)
- [ ] File contains orchestrator prompt
- [ ] File contains role → agent mapping table
- [ ] File contains all 5 role prompts
- [ ] File is readable and properly formatted

### Workflow Verification
- [ ] Orchestrator launches successfully
- [ ] Planner generates detailed plan
- [ ] Validator reviews and approves plan
- [ ] Implementer creates code files
- [ ] Reviewer examines implementation
- [ ] Fixer addresses any issues (if needed)
- [ ] Final code meets all requirements

### Code Quality Verification
- [ ] Function has correct type hints
- [ ] Function has comprehensive docstring
- [ ] Function implementation is correct
- [ ] Unit tests are comprehensive
- [ ] All tests pass
- [ ] Code follows Python best practices

## Troubleshooting

### Issue: Launcher fails with "Config file not found"

**Solution:**
- Verify `config.toml` exists in `/root/brainchain/`
- Verify file is readable: `cat config.toml`
- Check for syntax errors: `python3 -c "import tomllib; tomllib.load(open('config.toml', 'rb'))"`

### Issue: Launcher fails with "Prompt file not found"

**Solution:**
- Verify all prompt files exist in `prompts/` directory:
  ```bash
  ls -la prompts/
  ```
- Expected files:
  - `orchestrator.md`
  - `planner.md`
  - `plan_validator.md`
  - `implementer.md`
  - `code_reviewer.md`
  - `fixer.md`

### Issue: Claude CLI doesn't open

**Solution:**
- Verify Claude CLI is installed: `claude --version`
- Verify Claude CLI is in PATH: `which claude`
- Try launching Claude directly: `claude --model opus`
- Check for authentication issues: `claude auth status`

### Issue: Codex CLI doesn't open

**Solution:**
- Verify Codex CLI is installed: `codex --version`
- Verify Codex CLI is in PATH: `which codex`
- Try launching Codex directly: `codex --help`
- Check for authentication issues

### Issue: Agent doesn't receive prompt

**Solution:**
- Verify prompt is being passed correctly
- Check `.orchestrator_context.md` was created
- Verify prompt content is not truncated (max 10,000 chars for Claude)
- Try launching role directly: `python3 brainchain.py --role planner`

### Issue: Workflow doesn't proceed to next stage

**Solution:**
- Verify orchestrator received previous stage output
- Check if agent output is in expected format
- Verify orchestrator has access to subprocess module
- Check for file permission issues

### Issue: Tests fail

**Solution:**
- Verify Python 3.11+ is installed: `python3 --version`
- Verify test files are created correctly
- Run tests manually: `python3 -m pytest test_add_numbers.py -v`
- Check for import errors or missing dependencies

## Manual Testing Workflow

If you want to test individual roles without the full orchestrator:

### Test Planner Role Directly

```bash
python3 brainchain.py --role planner
```

Then provide a request to the planner.

### Test Implementer Role Directly

```bash
python3 brainchain.py --role implementer
```

Then provide a plan to the implementer.

### Test Reviewer Role Directly

```bash
python3 brainchain.py --role code_reviewer
```

Then provide implementation to the reviewer.

## Performance Expectations

- **Planner:** 30-60 seconds (generates detailed plan)
- **Validator:** 20-40 seconds (reviews plan)
- **Implementer:** 60-120 seconds (creates code and tests)
- **Reviewer:** 30-60 seconds (analyzes code)
- **Fixer:** 30-60 seconds (if needed)
- **Total workflow:** 3-5 minutes for simple task

## Success Criteria

The E2E test is successful when:

1. ✅ Launcher starts without errors
2. ✅ Context file created with full system context
3. ✅ Orchestrator prompt loaded correctly
4. ✅ All role prompts available in context
5. ✅ Planner generates structured plan
6. ✅ Validator reviews and approves plan
7. ✅ Implementer creates code files
8. ✅ Code follows requirements and best practices
9. ✅ Reviewer approves implementation
10. ✅ Final output is production-ready

## Notes

- **Full E2E requires manual interaction:** The orchestrator coordinates agents via subprocess, but you must manually provide input at each stage and observe the workflow.
- **Context file is essential:** The `.orchestrator_context.md` file contains all prompts and role mappings. It's created automatically when the launcher runs.
- **Agent availability:** The test requires both Claude CLI and Codex CLI to be installed and authenticated.
- **File ownership:** Each stage creates/modifies specific files. Verify no conflicts occur between stages.
- **Idempotency:** You can run the test multiple times. Each run creates fresh context and files.

## Next Steps

After successful E2E test:

1. Document any issues or unexpected behaviors
2. Verify all acceptance criteria from plan are met
3. Consider edge cases and stress testing
4. Document lessons learned
5. Archive test results for reference

---

**Last Updated:** 2026-01-20  
**Test Status:** Ready for manual execution  
**Launcher Status:** ✅ Verified working

---
name: work
description: Fast disciplined work with constitutional compliance and task tracking
argument-hint: "detailed instructions for what you want implemented"
allowed-tools: Read, Write, Bash, Grep, Glob, TodoWrite
---

Execute work fast with strict constitutional compliance and task tracking. For non-complex tasks requiring a disciplined process.

## Usage

```bash
/fast-work <detailed instructions>
```

## Process Flow

1. **Plan** - Analyze instructions, identify tasks
2. **Track** - TodoWrite for progress tracking
3. **Execute** - Implement with constitutional compliance
4. **Verify** - Mandatory linting quality gate
5. **Complete** - Summary of changes

## Steps

### 1. Validate & Plan

```
INSTRUCTIONS = $ARGUMENTS

If empty:
  Display: "Error: Instructions required. Usage: /fast-work <instructions>"
  Exit

Read @.claude/constitution.md - internalize NON-NEGOTIABLE principles:
- I. Radical Simplicity (functions <10 complexity, <50 statements)
- II. Fail Fast (no defensive code, no blind exceptions)
- III. Type Safety (hints everywhere)
- IV. Structured Data (Pydantic/dataclasses, not dicts)
- V. Unit Testing (appropriate mocking)
- VI. Dependency Injection (all deps REQUIRED, no Optional/defaults)
- VII. SOLID Principles

Analyze instructions into specific tasks:
- Keep tasks atomic and measurable
- Note applicable constitutional principles
```

### 2. Track

```
Create TodoWrite task list:
[
  {
    "content": "Task description",
    "status": "pending",
    "activeForm": "Task description in progress form"
  },
  ...
]
```

### 3. Execute

```
FOR EACH TASK:

  Update TodoWrite: status = "in_progress"

  Implement following constitutional principles:
  - Radical Simplicity - simplest approach
  - Type Hints everywhere
  - Pydantic/dataclasses for data
  - Dependency Injection (all deps REQUIRED)
  - SOLID principles
  - Fail Fast - no defensive programming
  - Unit tests with mocking

  LINTING QUALITY GATE (MANDATORY):
  1. ruff format {modified_files}
  2. ruff check --fix {modified_files}
  3. ruff check {modified_files}
  4. If violations: STOP and fix:
     - C901/PLR0915 → refactor (VIOLATES Principle I)
     - BLE001 → specific exceptions (VIOLATES Principle II)
     - PERF203 → optimize
     - A002 → rename
     - FBT* → named params
     - SIM* → simplify
  5. Re-run: ruff check {modified_files}
  6. ONLY proceed when ZERO violations

  Update TodoWrite: status = "completed"

END FOR
```

### 4. Complete

```
Display concise summary:
- Tasks completed
- Files changed (paths + type)
- Constitutional compliance status
- Brief summary
- Next steps (if any)
```

## Constitutional Compliance

Every task must verify:
- ✓ Radical Simplicity (functions <10 complexity, <50 statements)
- ✓ Fail Fast (no defensive code, no blind exceptions)
- ✓ Type Safety (hints everywhere)
- ✓ Structured Data (Pydantic/dataclasses)
- ✓ Unit Testing (appropriate mocking)
- ✓ Dependency Injection (all deps REQUIRED)
- ✓ SOLID Principles
- ✓ Linting Clean (ZERO violations - MANDATORY)

## Notes

**Use for:** Non-complex tasks needing disciplined implementation (features, refactoring, tests, services)

**Tasks:** Atomic, specific, measurable, ordered

**Quality Gate:** MANDATORY linting (ruff format + ruff check --fix + ruff check = ZERO violations)

## See Also

- `/generate-spec` - For complex features
- `/execute-tasks` - For task files with review loop
- `@.claude/constitution.md` - Full principles
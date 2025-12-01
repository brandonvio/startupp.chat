---
name: work
description: Execute work from prompt through automated spec-task-execute-review cycle
argument-hint: "detailed instructions for what you want implemented"
allowed-tools: Read, Write, Bash, Grep, Glob, TodoWrite
---

Execute work based on user instructions through automated constitutional workflow with review-refine loop.

## Usage

```bash
/work <detailed instructions>
```

## Examples

```bash
/work Add Pydantic model support to MongoDB service mirroring Redis pattern
/work Create a new user authentication service with email validation
/work Refactor the payment service to use dependency injection
```

## Process Overview

This command orchestrates a complete workflow through specialized agents:

1. **Specification Generation** → constitution-spec-generator creates spec from prompt
2. **Task Generation** → constitution-task-generator creates tasks from spec
3. **Task Execution** → constitution-task-executor implements all tasks
4. **Code Review** → constitution-code-reviewer audits against constitution
5. **Refinement Loop** → Repeat steps 3-4 until constitutional approval

## Workflow Steps

### 1. Validate Input

```
INSTRUCTIONS = $ARGUMENTS

If INSTRUCTIONS is empty:
  Display: "Error: Work instructions required."
  Display: "Usage: /work <detailed instructions>"
  Exit
```

### 2. Generate Specification

Invoke **constitution-spec-generator**:

```
Generate a comprehensive technical specification from the user's requirements:

{INSTRUCTIONS}

Analyze the codebase systematically and follow the standardized 15-section specification format.
Save to: specs/work-{timestamp}/work-spec.md
```

### 3. Generate Tasks

Invoke **constitution-task-generator**:

```
Generate a comprehensive task breakdown for the specification file created in step 2.

Read @.claude/constitution.md and ensure all tasks comply with all 7 constitutional principles.
Save to: specs/work-{timestamp}/work-tasks.md
```

### 4. Review-Refine Loop

Execute the following loop until approval:

```
ITERATION = 0
MAX_ITERATIONS = 5
APPROVED = false
CURRENT_TASKS_FILE = tasks file from step 3

WHILE NOT APPROVED AND ITERATION < MAX_ITERATIONS:
  ITERATION = ITERATION + 1

  Display: "═══════════════════════════════════════════════════════"
  Display: "Iteration {ITERATION}: Executing tasks..."
  Display: "═══════════════════════════════════════════════════════"

  # Execute Tasks
  Invoke constitution-task-executor:
    Execute ALL tasks from: {CURRENT_TASKS_FILE}

    PRIMARY MANDATE: Execute ALL tasks from start to finish WITHOUT stopping.
    Apply all 7 constitutional principles.
    Update ALL checkboxes in real-time.

  # Review Implementation
  Invoke constitution-code-reviewer:
    Review implementation from tasks file: {CURRENT_TASKS_FILE}

    PRIMARY MANDATE: Comprehensive constitutional audit of all implemented code.
    Generate output:
      - If issues found: Create work-r{ITERATION}-tasks.md
      - If approved: Create work-r{ITERATION}-approval.md

  # Check Review Result
  If approval file exists:
    APPROVED = true
    Display: "✅ CONSTITUTIONAL APPROVAL GRANTED"
    Break loop

  Else if refinement file exists:
    Display: "⚠️  Issues Found - Refinement Required"
    CURRENT_TASKS_FILE = refinement file
    Continue loop

  Else:
    Display: "Error: Code reviewer did not generate output"
    Exit

END WHILE
```

### 5. Handle Completion

```
If APPROVED:
  Display: "════════════════════════════════════════════════════════════"
  Display: "                    WORK COMPLETE"
  Display: "════════════════════════════════════════════════════════════"
  Display: "Status: ✅ APPROVED"
  Display: "Iterations: {ITERATION}"
  Display: "Final Approval: {approval_file_path}"
  Display: ""
  Display: "Next Steps:"
  Display: "  1. Review approval document for details"
  Display: "  2. Run full test suite if available"
  Display: "  3. Commit changes with /commit"
  Display: "════════════════════════════════════════════════════════════"

Else:
  Display: "════════════════════════════════════════════════════════════"
  Display: "                    MAXIMUM ITERATIONS REACHED"
  Display: "════════════════════════════════════════════════════════════"
  Display: "Status: ⚠️  NOT APPROVED"
  Display: "Iterations: {ITERATION}"
  Display: "Last Task File: {CURRENT_TASKS_FILE}"
  Display: ""
  Display: "Review the latest refinement tasks and address issues manually."
  Display: "════════════════════════════════════════════════════════════"
```

## Notes

- All implementation logic lives in the specialized agents
- This command orchestrates the workflow, agents do the heavy lifting
- Automatic review-refine loop ensures constitutional compliance
- Maximum 5 iterations before requiring manual intervention
- Each iteration produces either approval or refinement tasks

## See Also

- Constitution Spec Generator Agent
- Constitution Task Generator Agent
- Constitution Task Executor Agent
- Constitution Code Reviewer Agent
- `@.claude/constitution.md` - Full constitutional principles

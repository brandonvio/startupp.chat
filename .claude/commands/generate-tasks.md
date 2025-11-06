---
name: generate-tasks
description: Generate comprehensive task breakdown from specification file using constitution-task-generator agent
argument-hint: "path/to/spec-file.md"
allowed-tools: Read, Task
---

Generate a comprehensive, constitution-compliant task breakdown by invoking the constitution-task-generator agent.

## Usage

```bash
/generate-tasks path/to/spec-file.md
```

## Examples

```bash
/generate-tasks spec/feature-specification.md
/generate-tasks spec/parallel-pipeline.md
/generate-tasks spec/model-by-task.md
```

## Steps

### 1. Validate Input

```
SPEC_FILE = $1

If SPEC_FILE is empty:
  Display: "Error: Specification file path required."
  Display: "Usage: /generate-tasks path/to/spec-file.md"
  Exit

If SPEC_FILE doesn't exist:
  Display: "Error: Specification file not found: $SPEC_FILE"
  Exit
```

### 2. Invoke Agent

Invoke the **constitution-task-generator** agent with:

```
Generate a comprehensive task breakdown for the specification file: $SPEC_FILE

Read the project constitution at @.claude/constitution.md and ensure all tasks comply with:
- Radical Simplicity
- Fail Fast Philosophy
- Comprehensive Type Safety
- Structured Data Models
- Unit Testing with Mocking
- Dependency Injection
- SOLID Principles

Save the tasks file as: {spec-basename}-tasks.md in the same directory as the spec file.
```

### 3. Report Success

After agent completes:
- Confirm tasks file location (absolute path)
- Display success message
- Suggest next steps: review tasks, then use /execute-tasks

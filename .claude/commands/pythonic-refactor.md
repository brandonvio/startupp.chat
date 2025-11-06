---
name: pythonic-refactor
description: Add type hints and refactor Python code to use Pydantic models without breaking interfaces
argument-hint: "path/to/python_file.py"
allowed-tools: Read, Task
---

Refactor Python code to add type hints and use Pydantic models by invoking the pydantic-refactor-specialist agent.

## Usage

```bash
/pythonic-refactor path/to/file.py
```

## Examples

```bash
/pythonic-refactor src/models/user.py
/pythonic-refactor src/services/notification_service.py
```

## Steps

### 1. Validate Input

```
PYTHON_FILE = $1

If PYTHON_FILE is empty:
  Display: "Error: Python file path required."
  Display: "Usage: /pythonic-refactor path/to/file.py"
  Exit

If PYTHON_FILE doesn't exist:
  Display: "Error: Python file not found: $PYTHON_FILE"
  Exit

If PYTHON_FILE doesn't end with ".py":
  Display: "Warning: File doesn't appear to be a Python file"
  Display: "Proceeding anyway..."
```

### 2. Invoke Agent

Invoke the **pydantic-refactor-specialist** agent with:

```
Refactor the Python file at: $PYTHON_FILE

Requirements:
1. Add comprehensive type hints to all functions, methods, and class attributes
2. Convert appropriate data structures to Pydantic models (BaseModel)
3. Maintain 100% backward compatibility with existing interfaces
4. Use Pydantic validation features (validators, Field constraints)
5. Follow Python best practices and PEP 8
6. Add docstrings if missing

CRITICAL: Preserve external interfaces. All public methods must maintain original signatures.
Use Pydantic model.model_dump() for dict compatibility where needed.
```

### 3. Report Success

After agent completes:
- Confirm file was refactored
- Summarize changes made
- Suggest running tests to verify compatibility

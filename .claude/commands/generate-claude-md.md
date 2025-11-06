---
name: generate-claude-md
description: Generate comprehensive CLAUDE.md documentation for a folder using the claude-md-generator agent
argument-hint: "path/to/folder (optional, defaults to current directory)"
allowed-tools: Read, Glob, Task
---

Generate comprehensive CLAUDE.md documentation by invoking the claude-md-generator agent to analyze a folder's structure and contents.

## Usage

```bash
# Document current directory
/generate-claude-md

# Document specific folder
/generate-claude-md src/services

# Document with absolute path
/generate-claude-md /Users/brandon/code/projects/lvrgd/lvrgd-common/src/models
```

## Steps

### 1. Determine Target Path

```
TARGET_PATH = $ARGUMENTS (if provided) or "." (current directory)
```

### 2. Validate Path

Use Glob to verify the path exists and contains files:
- Try: `$TARGET_PATH/**/*`
- If no results and path doesn't exist: Show error
- If path is a file: Show error (must be directory)

### 3. Invoke Agent

Invoke the **claude-md-generator** agent with:

```
Please analyze and generate comprehensive CLAUDE.md documentation for the folder at: $TARGET_PATH

The folder is part of a Python project using pytest, MinIO, and Make for build automation.

Generate a CLAUDE.md file that includes:
- Constitution Compliance section (MANDATORY)
- Component functionality and architecture
- File organization and structure
- Usage examples and best practices
- Development setup and commands

Save the CLAUDE.md file in the root of the analyzed directory: $TARGET_PATH/CLAUDE.md
```

### 4. Report Success

After agent completes, confirm:
- File location (absolute path)
- Brief summary of what was documented
- Next steps (review, edit, commit)

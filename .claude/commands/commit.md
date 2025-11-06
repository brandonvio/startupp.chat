---
title: commit
description: Stage all changes and commit with auto-generated message
allowed-tools: Task
---

Stage all changes, validate code quality, generate a conventional commit message, and push to remote by invoking the commit-agent.

## Usage

```bash
/commit
```

## Steps

### 1. Invoke Agent

Invoke the **commit-agent** with:

```
Validate code quality, analyze all changes, generate a meaningful commit message following repository conventions, create the commit, and push to remote.
```

### 2. Review Results

After agent completes:
- Verify commit was created successfully
- Confirm changes were pushed to remote
- Review commit message for accuracy

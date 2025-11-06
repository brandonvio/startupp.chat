---
name: generate-agent
description: Generate a new Claude Code subagent using the agent-generator specialist
argument-hint: "description of what the agent should do"
allowed-tools: Task
---

Generate a new Claude Code subagent by invoking the agent-generator specialist.

## Usage

```bash
/generate-agent "description of what the agent should do"
```

## Examples

```bash
/generate-agent "database query optimizer that analyzes and improves SQL performance"
```

```bash
/generate-agent "security auditor that scans code for vulnerabilities"
```

```bash
/generate-agent "API documentation generator that creates OpenAPI specs"
```

## Steps

### 1. Validate Input

```
AGENT_DESCRIPTION = $1

If AGENT_DESCRIPTION is empty:
  Display: "Error: Agent description required."
  Display: "Usage: /generate-agent \"description of what the agent should do\""
  Display: ""
  Display: "Example: /generate-agent \"database optimizer for SQL queries\""
  Exit
```

### 2. Invoke Agent

Invoke the **agent-generator** agent with:

```
Create a new Claude Code subagent based on the following requirements:

$AGENT_DESCRIPTION

Please:
1. Analyze the requirements and determine the appropriate:
   - Agent name (following lowercase-hyphen convention)
   - Tools needed for this agent's purpose
   - Level of proactivity (automatic vs explicit invocation)
   - Expertise domain and tone

2. Create a comprehensive subagent with:
   - Proper YAML frontmatter
   - Clear, action-oriented description
   - Detailed system prompt with role definition
   - Step-by-step processes and workflows
   - Quality standards and best practices
   - Appropriate tool selection

3. Save the agent to .claude/agents/ directory

Ensure the agent follows all best practices from the agent-generator guidelines.
```

### 3. Report Success

After agent completes:
- Confirm agent file location (absolute path)
- Display agent name and description
- Suggest testing the agent with a relevant task
- Note: Agent is now available for use via the Task tool or explicit invocation

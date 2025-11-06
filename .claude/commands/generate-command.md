---
name: generate-command
description: Generate a new slash command by describing what it should do
argument-hint: "description of what the command should do"
allowed-tools: Read, Write, Glob, Grep, Agent
---

Invoke the slash-command-generator agent to create a new custom slash command based on your description.

This meta-command acts as a convenient wrapper for generating new slash commands without needing to manually invoke the agent. Simply describe what you want the command to do, and the slash-command-generator agent will analyze the requirements, design the command structure, and create a complete, working slash command file in the `.claude/commands/` directory.

## Usage

```bash
/generate-command "description of what the command should do"
```

## Examples

```bash
# Generate a test runner command with coverage
/generate-command "Run all tests and generate a coverage report"

# Generate a deployment command
/generate-command "Deploy the application to staging environment"

# Generate a documentation generator
/generate-command "Generate API documentation from Python docstrings"

# Generate a code analysis command
/generate-command "Analyze code complexity and suggest refactoring opportunities"

# Generate a database migration command
/generate-command "Create and apply database migrations using Alembic"
```

## Steps

### 1. Validate Input
- Check if a command description is provided via $ARGUMENTS
- If no description provided, display usage message and exit
- Verify the description is sufficiently detailed (at least 10 characters)
- If description is too short, prompt for more details

### 2. Provide Context to Agent
Before invoking the agent, gather relevant project context:
- Read existing slash commands to understand project patterns
- Check project structure (pyproject.toml, README, etc.) for technology stack
- Identify testing frameworks, build tools, and common workflows
- Note any project-specific conventions or standards

### 3. Invoke Slash Command Generator Agent
Call the slash-command-generator agent with:
- The user's command description from $ARGUMENTS
- Project context and existing command patterns
- Request that the agent:
  - Analyze the requirements and ask clarifying questions if needed
  - Design an appropriate command structure
  - Generate a complete, well-documented slash command
  - Save the command to `.claude/commands/` directory
  - Follow project conventions and best practices

### 4. Report Success
After the agent completes, provide summary:
- Confirm the new command name and file location (absolute path)
- Show example usage of the newly created command
- List the key features and capabilities of the command
- Provide any next steps or recommendations

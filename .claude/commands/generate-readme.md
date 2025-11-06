---
name: generate-readme
description: Generate or update README.md file using the readme-generator agent
argument-hint: "[path/to/project] (optional, defaults to current directory)"
allowed-tools: Task, Read
---

Generate or update a README.md file by invoking the readme-generator agent.

## Usage

```bash
/generate-readme [path/to/project]
```

If no path is provided, the command operates on the current directory.

## Examples

```bash
# Generate README for current directory
/generate-readme
```

```bash
# Generate README for specific project
/generate-readme src/my-library
```

```bash
# Update existing README at project root
/generate-readme .
```

## Steps

### 1. Determine Target Path

```
PROJECT_PATH = $1

If PROJECT_PATH is empty:
  PROJECT_PATH = current working directory
  Display: "Using current directory for README generation"

If PROJECT_PATH does not exist:
  Display: "Error: Path not found: $PROJECT_PATH"
  Exit
```

### 2. Invoke Agent

Invoke the **readme-generator** agent with:

```
Generate or update the README.md file for the project located at: $PROJECT_PATH

Please:
1. Analyze the project structure thoroughly, examining:
   - Package manifests and dependency files
   - Configuration files and environment requirements
   - Source code structure and key entry points
   - Existing documentation files
   - Test setup and build processes

2. Check for existing README.md and analyze git history if present:
   - Identify when README was last updated
   - Determine what has changed in the project since
   - Preserve existing voice and custom sections
   - Identify outdated content that needs updates

3. Create or update README.md following GitHub best practices:
   - Craft compelling project description and tagline
   - Include relevant badges (build, version, license, etc.)
   - Provide clear installation and setup instructions
   - Include practical usage examples
   - Add appropriate visual elements (emojis, tables, code blocks)
   - Ensure technical accuracy of all examples

4. Ensure the README addresses:
   - What is this project?
   - Why should someone use it?
   - How do they get started?
   - How do they use it?
   - Where can they get help?
   - How can they contribute?

5. Save the README.md file in the project directory

Deliver a visually engaging, technically accurate, and comprehensive README that serves as an effective entry point for users, contributors, and maintainers.
```

### 3. Report Success

After agent completes:
- Confirm README.md file location (absolute path)
- Note whether this was a new creation or an update
- Highlight key sections included in the README
- Suggest reviewing the README and adding any mentioned visual assets (screenshots, diagrams)

---
name: generate-spec
description: Generate comprehensive technical specification from prompt file or direct input using spec-generator agent
argument-hint: "[specs/prompt-file.md] (optional)"
allowed-tools: Read, Task
---

Generate a comprehensive, standardized technical specification document by invoking the spec-generator agent.

## Usage

```bash
# From prompt file in specs folder
/generate-spec specs/feature-prompt.md

# From direct description (provide requirements when prompted)
/generate-spec
```

## Examples

```bash
# Generate spec from existing prompt file
/generate-spec specs/auth-feature-prompt.md
/generate-spec specs/websocket-support-prompt.md

# Generate spec from direct prompt
/generate-spec
# Then provide: "Add WebSocket support to messaging with real-time updates"
```

## Steps

### 1. Validate Input (if file path provided)

```
PROMPT_FILE = $1

If PROMPT_FILE is provided:
  If PROMPT_FILE doesn't exist:
    Display: "Error: Prompt file not found: $PROMPT_FILE"
    Exit

  If PROMPT_FILE is not in specs folder:
    Display: "Error: Prompt file must be in specs folder."
    Display: "Provided: $PROMPT_FILE"
    Display: "Expected: specs/[filename].md"
    Exit
```

### 2. Invoke Agent

Invoke the **spec-generator** agent with:

**If prompt file provided:**
```
Generate a comprehensive technical specification from the prompt file: @$PROMPT_FILE

Analyze the codebase systematically:
- Identify affected components and integration points
- Determine file structure and naming conventions
- Map dependencies and architecture patterns
- Review existing similar features for consistency

Follow the standardized 15-section specification format.
Save the specification as: specs/{basename}-spec.md (replace -prompt.md with -spec.md)
```

**If no file provided (direct prompt):**
```
Generate a comprehensive technical specification from the user's requirements.

The user will provide requirements directly. Analyze them and:
- Identify affected components and integration points
- Determine file structure and naming conventions
- Map dependencies and architecture patterns
- Review existing similar features for consistency

Follow the standardized 15-section specification format.
Ask the user for the preferred spec filename or suggest based on the feature name.
Save to specs/[feature-name]-spec.md using kebab-case naming.
```

### 3. Report Success

After agent completes:
- Confirm specification file location (absolute path)
- Display specification summary:
  - Components affected (modified/new files)
  - Requirements identified (functional/non-functional)
  - Test files needed
  - Dependencies (new/modified)
- Suggest next steps: review spec, address open questions, use as implementation guide

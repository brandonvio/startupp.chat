---
name: format-md
description: Improve markdown file clarity, conciseness, and formatting
argument-hint: "path/to/file.md"
allowed-tools: Read, Write
---

Improve a markdown file for clarity, conciseness, and proper formatting while maintaining the original content's meaning.

## Usage

```
/format-md path/to/file.md
```

## Processing Steps

### 1. Validate Input

- Check if $1 (file path) is provided
  - If empty, show usage: "Usage: /format-md <path/to/file.md>"
  - Exit if no argument provided

### 2. Read File

- Read the markdown file at the specified path: $1
- If file doesn't exist, show error: "Error: File not found at $1"
- Validate the file path is within the project directory

### 3. Detect Spec Folder

- Check if the file path contains `spec/`
- If YES: This is a specification document requiring constitution compliance
- If NO: This is a regular markdown document

### 4. Apply Formatting Improvements

**Markdown Structure:**
- Fix heading hierarchy (ensure proper H1 → H2 → H3 nesting)
- Improve list formatting (consistent bullet/number styles)
- Add proper code block syntax highlighting
- Format tables with proper alignment
- Add blank lines for visual separation
- Fix inline code formatting with backticks
- Ensure proper link formatting
- Add horizontal rules for section breaks where appropriate

**Content Clarity:**
- Break up long paragraphs
- Convert walls of text to bullet lists
- Add emphasis (bold/italic) for key terms
- Improve section organization
- Remove redundant content
- Fix grammar and punctuation
- Ensure consistent terminology

**Conciseness:**
- Remove unnecessary words
- Simplify complex sentences
- Eliminate redundancy
- Use active voice
- Make technical content scannable

### 5. Add Constitution Section (Spec Files Only)

If the file path contains `spec/`, insert this section **after the title/H1 heading**:

```markdown
## Constitution Compliance

This specification must follow the principles defined in [constitution.md](@.claude/constitution.md):
- **Radical Simplicity**: Implement the simplest solution
- **Fail Fast**: No defensive fallbacks unless explicitly required
- **Type Safety**: Comprehensive type hints everywhere
- **Structured Data**: Use Pydantic models or dataclasses
- **Dependency Injection**: All services must use DI
- **SOLID Principles**: Strict adherence required
```

**Placement Rules:**
- Place AFTER the main title (H1)
- Place BEFORE the first major content section
- If an "Overview" or similar section exists, place before it
- Add blank lines before and after for readability

### 6. Save Improved File

- Write the improved content back to the original file path: $1
- Preserve the original file location
- No backup needed (git tracks changes)

### 7. Report Changes

Generate a summary of improvements made:

**Success Message:**
```
✓ Successfully formatted: $1

Changes applied:
- [List specific improvements, e.g.:]
- Fixed heading hierarchy (H1→H2→H3)
- Improved list formatting (3 lists)
- Added code block syntax highlighting (Python, JSON)
- Broke up 2 long paragraphs
- Added constitution compliance section (spec file)
- Improved table formatting
- Added section separators
```

## Examples

### Example 1: Regular Markdown File
```
/format-md README.md
```

Output:
```
✓ Successfully formatted: /path/to/project/README.md

Changes applied:
- Fixed heading hierarchy
- Improved code block syntax (Bash, Python)
- Added blank lines between sections
- Converted 2 paragraphs to bullet lists
```

### Example 2: Spec File
```
/format-md spec/feature-specification.md
```

Output:
```
✓ Successfully formatted: /path/to/project/spec/feature-specification.md

Changes applied:
- Added constitution compliance section
- Fixed heading hierarchy
- Improved list formatting
- Added code block syntax highlighting (Python)
- Broke up 3 long paragraphs
- Added emphasis to key terms
```

### Example 3: Missing File
```
/format-md spec/nonexistent.md
```

Output:
```
✗ Error: File not found at /path/to/project/spec/nonexistent.md

Usage: /format-md <path/to/file.md>
```

## Error Handling

### Missing Argument
- Show usage example
- Explain expected input format

### File Not Found
- Display clear error with attempted path
- Suggest checking file path or using file picker

### Invalid Path
- Validate path is within project directory
- Show error if attempting to access files outside project

### Read/Write Errors
- Show specific error message
- Suggest checking file permissions
- Verify file is not locked by another process

## Quality Standards

**Maintain:**
- Original content meaning and intent
- Technical accuracy
- Author's voice and tone
- Key terminology and naming

**Improve:**
- Document structure and navigation
- Visual hierarchy and scannability
- Code example clarity
- Consistency in formatting
- Professional presentation

**Add (Spec Files Only):**
- Constitution compliance section
- Clear reference to project principles
- Emphasis on architectural requirements

## Notes

- This command modifies files in place
- Git tracks all changes for easy rollback
- Constitution section only added to files in `spec/` folder
- Maintains markdown compatibility with common parsers
- Safe to run multiple times (idempotent for structure)

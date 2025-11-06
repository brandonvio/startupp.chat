---
name: generate-mr-doc
description: Generate merge request documentation by analyzing branch commits
argument-hint: "[branch-name] (optional - defaults to current branch)"
allowed-tools: Bash, Read, Write, Grep
---

Generate comprehensive merge request documentation by analyzing commits on the current branch compared to main. Creates a detailed document saved to docs/merge-request-summaries/ with sections for Summary, Changes Overview, Key Improvements, Technical Details, Testing Impact, and Quality Assurance.

Usage:
- `/generate-mr-doc` - Generate MR doc for current branch
- `/generate-mr-doc feature-branch` - Generate MR doc for specified branch

Steps:
1. Get current branch name or use provided branch name from $1
2. Ensure we're not on main branch (safety check)
3. Create docs/merge-request-summaries directory if it doesn't exist
4. Get commit differences between branch and main
   - Get changes to all files that have not yet been commited
5. Analyze file changes and generate statistics
6. Create comprehensive merge request documentation with:
   - Executive summary of changes
   - Detailed changes overview with file statistics
   - Key improvements and technical enhancements
   - Technical implementation details
   - Testing impact assessment
   - Quality assurance checklist
7. Save document as docs/merge-request-summaries/{branch-name}.md
8. Display completion message with file location

Example output sections:
- **Summary**: High-level overview of the merge request purpose
- **Changes Overview**: File modifications, additions, deletions with statistics
- **Key Improvements**: Major enhancements, features, or fixes
- **Technical Details**: Implementation specifics, architecture changes
- **Testing Impact**: How changes affect testing, new test coverage
- **Quality Assurance**: Code standards compliance, validation checks

The generated document follows the repository's documentation standards and provides comprehensive information for code reviewers and stakeholders.
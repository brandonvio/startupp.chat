---
name: code-review
description: Perform comprehensive code review of current git branch changes
---

Perform a comprehensive code review of all changes in the current git branch compared to the main branch.

## Review Process

### 1. Git Analysis
- Identify current branch name: `git branch --show-current`
- List all changed files: `git diff --stat main...HEAD`
- Show detailed changes: `git diff main...HEAD`
- Review commit history: `git log main..HEAD --oneline`

### 2. Code Quality Assessment

Analyze all changed files for:

**Python Code Quality:**
- PEP 8 compliance and formatting
- Type hints completeness and correctness
- Function/class structure and organization
- Error handling patterns
- Code complexity and maintainability
- Performance considerations

**Framework-Specific Patterns:**
- Handler/endpoint implementation structure
- Environment variable usage
- External service client initialization
- Error response formatting
- Resource management

### 3. Security Review

Check for:
- Hardcoded credentials or API keys
- Input validation and sanitization
- SQL/NoSQL injection vulnerabilities
- Sensitive data in logs or error messages
- IAM permission configurations
- Encryption settings (at rest and in transit)
- Authentication and authorization mechanisms

### 4. Architecture Compliance

Verify:
- Adherence to project patterns and conventions
- Service layer structure and dependency injection
- Best practices (retry logic, timeouts, error handling)
- Infrastructure as Code quality (if applicable)
- Integration with existing systems
- Backwards compatibility

### 5. Testing Assessment

Evaluate:
- Unit test coverage for new/modified code
- Integration test adequacy
- Test quality and assertions
- Mock usage and test fixtures
- Error condition and edge case testing
- Test documentation

### 6. Documentation Review

Check:
- Code comments and docstrings
- README.md or CLAUDE.md updates needed
- API documentation (if applicable)
- Inline comments for complex logic
- Migration guides (if breaking changes)

## Output Format

Provide a structured review report with:

### Executive Summary
- Branch name and files changed count
- Overall recommendation: **Approve** / **Request Changes** / **Needs Discussion**
- Critical issues requiring immediate attention

### Detailed Findings

#### 🔍 Code Quality
- Style and formatting issues
- Type hints and documentation
- Structure and organization improvements

#### 🔒 Security Review
- Vulnerabilities identified
- Authentication/authorization concerns
- Data handling issues

#### 🏗️ Architecture Compliance
- Pattern adherence
- Best practices compliance
- Infrastructure quality

#### 🧪 Testing Assessment
- Coverage analysis
- Test quality evaluation
- Missing test scenarios

#### 📚 Documentation
- Documentation completeness
- Updates needed

### Actionable Recommendations

1. **🚨 Critical** (Must fix before merge)
2. **⚠️ Important** (Should address)
3. **💡 Suggestions** (Consider for future)
4. **✅ Positive Highlights** (Good practices observed)

### Pre-Merge Checklist
- [ ] All critical issues resolved
- [ ] Security vulnerabilities addressed
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No breaking changes without handling
- [ ] Code style compliant

Be thorough, constructive, and provide specific examples with file paths and line numbers where applicable.

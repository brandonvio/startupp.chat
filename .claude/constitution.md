# Software Development Constitution

## Core Principles

### I. Radical Simplicity (NON-NEGOTIABLE)
**Always implement the simplest solution.**
- Never make code more complicated than it needs to be
- If you believe something needs to increase in complexity, do not do it
- Always keep it simple
- We aren't building a space shuttle
- Keep things simple, easy to understand, and easy to maintain

### II. Fail Fast Philosophy (NON-NEGOTIABLE)
**Systems should fail immediately when assumptions are violated.**
- Do not implement "fallback" code unless directly asked to
- Minimize checks on types and instances for precautionary purposes
- If something is not the right type or instance, the function needs to fail
- Do not check for existence of keys if the key is necessary to the process - the system should fail
- Trust that required data exists - let it fail if it doesn't

### III. Comprehensive Type Safety (NON-NEGOTIABLE)
**Use type hints everywhere possible.**
- Type hints must be used in ALL code: integration tests, unit tests, lambda functions, services, models
- !Use type hints according to best Python practices and idomatic Python code!
- Ensure each, every and all functions have type hints for parameters and return values, public or private
- Trust that the type exists - do not add runtime type checking
- Type hints are documentation and enable better tooling

### IV. Structured Data Models (NON-NEGOTIABLE)
**Always use dataclasses or Pydantic models when working with collections of data.**
- Never pass around dictionaries or loose data structures for structured data
- Use Pydantic when validation or serialization is needed
- Use dataclasses for simple data containers
- Models should be simple data definitions, not complex business logic

### V. Unit Testing with Mocking
Unit Testing is important, but should not be over-engineered or excessive.
Use appropriate mocking strategies in unit tests to ensure the system will work correctly. Mock external dependencies to ensure correct and expected system behavior.

### VI. Dependency Injection (NON-NEGOTIABLE)
**All services must use dependency injection for their dependencies.**
- Constructor injection is the primary pattern - inject dependencies through `__init__`
- **ALL dependencies are REQUIRED parameters** - no Optional, no default values
- **NEVER create dependencies inside constructors** - all dependencies must be passed in from outside
- Enable testability by allowing mock injection
- Make services loosely coupled and independently testable
- Constructor should fail if valid dependencies are not provided (fail fast)
- Example pattern: `def __init__(self, dependency: DependencyType)` - no Optional, no defaults

### VII. SOLID Principles (NON-NEGOTIABLE)
**Strictly adhere to all SOLID principles in system design.**
- **Single Responsibility**: Each class/function has one reason to change
- **Open/Closed**: Open for extension, closed for modification
- **Liskov Substitution**: Subtypes must be substitutable for their base types
- **Interface Segregation**: Many specific interfaces better than one general interface
- **Dependency Inversion**: Depend on abstractions, not concretions (see Section VI)
- Apply these principles consistently across all code
- Refactor when principles are violated

## Development Standards

### Code Quality Gates
- All code must follow the radical simplicity principle
- Type hints are mandatory - no exceptions
- Structured data models required for all data collections
- Dependency injection required for all services - all dependencies REQUIRED (no Optional, no defaults), never created in constructors
- SOLID principles must be followed in all design decisions
- No defensive programming unless explicitly requested
- Let systems fail fast and fail hard
- Clean up verbose comments and prioritize updating function docstrings
- Format files with appropriate linting

### Testing Requirements
- Unit tests must use appropriate mocking strategies for external services
- Type hints required in all test code
- Test the happy path and let edge cases fail
- No over-engineered test scenarios

### Model Design
- Pydantic models should be simple data definitions only
- No complex business logic in models
- No extensive helper methods unless absolutely necessary
- Business logic belongs in services, not models

## Governance

**These principles are NON-NEGOTIABLE.**
- All code reviews must verify strict compliance with these principles
- Any violation of simplicity, type safety, fail-fast, dependency injection, or SOLID principles must be rejected
- Complexity increases must be explicitly justified and approved
- When in doubt, choose the simpler solution
- Services without proper dependency injection must be refactored
- Services that create dependencies inside constructors must be refactored
- Services with Optional dependencies or default parameter values must be refactored
- SOLID violations indicate architectural debt and must be addressed

**Version**: 3.1.0 | **Ratified**: 2025-01-17 | **Last Amended**: 2025-11-05
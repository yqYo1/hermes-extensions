---
name: software-development-workflow
description: "Software development workflows: planning, TDD, debugging, and experimental spikes."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [software-development, planning, tdd, debugging, spike, prototyping, workflow]
    related_skills: [subagent-driven-development, specification-authoring, github-workflow]
---

# Software Development Workflow

Software development lifecycle workflows: planning implementations, test-driven development, systematic debugging, and throwaway feasibility spikes.

## When to Use

Load this skill when the user wants to:
- Plan an implementation (break down features into tasks)
- Practice test-driven development
- Debug a problem systematically
- Validate an idea with a throwaway prototype

## 1. Implementation Planning

### Planning Principles

- Break work into bite-sized, independently verifiable tasks
- Each task should have a clear definition of done
- Order tasks by dependency and risk
- Identify integration points early

### Plan Structure

```markdown
## Implementation Plan: [Feature Name]

### Overview
Brief description of what we're building and why.

### Tasks

#### Task 1: [Name]
- **Goal**: What this task achieves
- **Files to modify**: List of files
- **Key decisions**: Any architectural choices
- **Verification**: How to confirm it works
- **Estimated effort**: Small / Medium / Large

#### Task 2: [Name]
...

### Dependencies
- Task N depends on Task M
- External dependencies (APIs, libraries, etc.)

### Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ... | ... | ... | ... |

### Integration Points
- Where this feature touches existing code
- API contracts that must be maintained
- Database schema changes
```

### Compatibility Patterns

When refactoring or migrating code, maintain backward compatibility:

**Wrapper Pattern:**
```python
# Old API
class OldAPI:
    def do_thing(self, arg):
        return self._new_impl.process(arg)

# New implementation
class NewImpl:
    def process(self, arg):
        # New logic
        pass
```

**Metaclass Versioning:**
```python
class APIVersion(type):
    def __new__(mcs, name, bases, namespace, version=None):
        # Version-specific behavior
        return super().__new__(mcs, name, bases, namespace)
```

See `references/compatibility-wrapper-patterns.md` for detailed examples.
See `references/metaclass-api-versioning.md` for API versioning strategies.
See `references/refactoring-compatibility-checklist.md` for migration checklists.

## 2. Test-Driven Development

### TDD Cycle: RED → GREEN → REFACTOR

```
RED:    Write a failing test
GREEN:  Write the minimum code to pass
REFACTOR: Clean up while keeping tests green
         ↓
        RED (next test)
```

### Rules

1. **No production code without a failing test first**
2. **Write only enough test to fail** (compilation errors count as failures)
3. **Write only enough production code to pass** (no speculation)
4. **Refactor only with green tests**

### Test Structure

```python
# Arrange - Set up the test fixture
# Act     - Execute the code under test
# Assert  - Verify the expected outcome

def test_feature_does_x():
    # Arrange
    subject = Feature()
    
    # Act
    result = subject.do_x()
    
    # Assert
    assert result == expected
```

### When to Use TDD

| Scenario | TDD? | Reason |
|----------|------|--------|
| New feature with clear requirements | ✅ Yes | Requirements drive tests |
| Bug fix | ✅ Yes | Reproduce bug first, then fix |
| Exploratory coding | ⚠️ Partial | Spike first, then TDD |
| Pure refactoring | ⚠️ Partial | Keep tests green, may not add new |
| Integration with external API | ❌ No | Mock complexity too high |
| Configuration/UI tweaks | ❌ No | Not testable logic |

### Anti-Patterns

- **Testing implementation details** — test behavior, not internal state
- **Over-mocking** — mocks should simulate, not replace, real behavior
- **Slow tests** — unit tests should run in < 100ms each
- **Brittle tests** — tests that break on every refactoring

## 3. Systematic Debugging

### 4-Phase Debugging Method

```
Understand → Reproduce → Isolate → Fix
```

#### Phase 1: Understand

- Read error messages carefully (stack traces, logs)
- Identify the symptom vs the root cause
- Check recent changes (git log, recent commits)
- Review related documentation and specs

#### Phase 2: Reproduce

- Find the minimal steps to trigger the bug
- Create a minimal reproduction case
- Verify the bug occurs consistently
- Document the reproduction steps

#### Phase 3: Isolate

- Use binary search on code changes (git bisect)
- Add logging at key points
- Use debugger or print statements
- Eliminate variables one by one

#### Phase 4: Fix

- Understand WHY the bug occurs
- Fix the root cause, not the symptom
- Verify the fix with the reproduction case
- Add a regression test
- Check for similar bugs elsewhere

### Debugging Checklist

- [ ] Read the full error message (not just the first line)
- [ ] Check logs for context
- [ ] Verify the environment (dependencies, versions)
- [ ] Reproduce in a clean environment
- [ ] Check for race conditions (timing-dependent bugs)
- [ ] Verify assumptions (null checks, type checks)
- [ ] Look for off-by-one errors
- [ ] Check resource leaks (memory, file handles, connections)

### Session-Specific Debug Notes

See `references/` directory for detailed debugging notes from past sessions:
- `hermes-cron-memory-unavailable.md` — Cron job memory issues
- `http-endpoint-testing-routing-debug.md` — HTTP routing debugging
- `nix-egl-bad-parameter-investigation.md` — Nix EGL parameter issues
- `nix-gui-egl-debugging.md` — Nix GUI debugging

## 4. Spike (Throwaway Experiments)

### When to Spike

- Validating feasibility before committing to a build
- Comparing approaches (A vs B)
- Surfacing unknowns that research won't answer
- "Is this even possible?" questions

### When NOT to Spike

- Answer is knowable from docs — just research
- Work is production path — use planning instead
- Idea is already validated — jump to implementation

### Spike Process

```
Decompose → Research → Build → Verdict
   ↑______________________________↓
           iterate on findings
```

1. **Decompose** — Break into 2-5 independent feasibility questions
2. **Research** — Brief each spike, surface competing approaches, pick one
3. **Build** — One directory per spike, bias toward interactive demos
4. **Verdict** — VALIDATED | PARTIAL | INVALIDATED

### Spike Structure

```
spikes/
├── 001-websocket-streaming/
│   ├── README.md      # Question, approach, results, verdict
│   └── main.py        # Runnable prototype
└── 002a-pdf-parse-pdfjs/
    ├── README.md
    └── parse.js
```

### Verdict Template

```markdown
## Verdict: VALIDATED | PARTIAL | INVALIDATED

### What worked
- ...

### What didn't
- ...

### Surprises
- ...

### Recommendation for the real build
- ...
```

## 5. External Project Investigation

### When to Use

- Surveying configuration options for self-hosted open-source projects
- Understanding another project's settings, defaults, and recommendations
- Comparing upstream documentation against actual source code
- Producing a comprehensive reference for a project's operator-facing surface

### Investigation Workflow

```
Subagent Broad Survey → Source Code Verification → Structured Synthesis
```

1. **Subagent Broad Survey**
   - Delegate to a subagent with `web` and `terminal` toolsets
   - Instruct the subagent to: clone the repo, read `.env.template`, `config.toml.example`, `docker-compose.yml.example`, and the main settings/config source file
   - Ask for a structured dump of every setting, its default, and its description

2. **Source Code Verification**
   - The PM (main agent) reads the actual source files directly to confirm
   - Cross-check subagent claims against `read_file` / `search_files` on the cloned repo
   - Verify default values, validation constraints, and inter-setting dependencies

3. **Structured Synthesis**
   - Organize findings by functional category (DB, Auth, LLM, Cache, etc.)
   - For each item: setting name, default value, meaning, and recommendation
   - Flag required vs optional, deprecated vs current, and immutable-after-deploy items
   - Include a minimal working example (.env or config.toml snippet)

### Pitfalls

- **Trusting subagent summaries blindly** — always verify claims against source
- **Writing overly long files in one shot** — `write_file` has practical size limits; for very large docs, stream via `terminal` with heredoc or write section-by-section
- **Missing nested/env-delimiter settings** — many projects use `__` or `.` nesting; ensure the survey captures these
- **Ignoring validation rules** — source code validators (`@model_validator`, `@field_validator`) reveal constraints not visible in templates

### Output Template

```markdown
# [Project] Self-Host Configuration Guide

## 1. Setting Precedence
[How the project resolves conflicts between env vars, .env, config files, and defaults]

## 2. Required Settings
| # | Setting | Description | Recommended Value |

## 3. [Category] Settings
| Setting | Default | Description | Recommendation |

## 4. Deployment Notes
- Immutable-after-deploy settings
- Required external services (DB, cache, vector store)
- Process topology (API server + worker requirements)

## 5. Minimal Working Example
```

## Related Skills

- **subagent-driven-development**: Delegate implementation to parallel subagents
- **specification-authoring**: Write and maintain specifications
- **github-workflow**: PR lifecycle and code review
- **frontend-rewrite-planning**: Frontend-specific planning and migration

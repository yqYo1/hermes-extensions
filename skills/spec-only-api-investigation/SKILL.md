---
name: spec-only-api-investigation
description: "Investigate API definitions that exist only in specification documents (never implemented) across a fork or project hierarchy. Supplements api-compatibility-investigation for the spec-only case."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [git, specification, api-compat, investigation]
    related_skills: [api-compatibility-investigation, specification-audit]
---

# Spec-Only API Investigation

Investigate an API that exists in specification/design documents but has no implementation in any fork. This is common in actively-developed projects where specs are written before code.

## When to Use

- Code search for a function/method name returns zero results across all repos
- The user mentions "SPECIFICATION.md" or a design document as the source
- A PM design question references an API you've never seen implemented
- You need to determine backward-compatibility constraints for a planned API change

## Relationship to api-compatibility-investigation

This skill handles the **spec-only subcase** of the broader api-compatibility-investigation workflow. If the API is found in code, use the parent skill instead.

## Procedure

### 1. Locate the Specification Document

Search for specification/design documents that might define the API:

```
search_files(pattern="api_name", path=<repo-path>, file_glob=["SPECIFICATION.md", "*.md", "*.spec"])
```

Common locations:

- `<repo>/SPECIFICATION.md` (root)
- `<repo>/.worktree/<branch>/SPECIFICATION.md` (git worktree)
- `<repo>/docs/` or `<repo>/Docs/`
- Remote branches: `git log remotes/origin/* --oneline --grep="keyword" -- "*.md"`

### 2. Distinguish "Never Implemented" from "Was Removed"

Use git history to distinguish these two cases:

```bash
# Case A: Never implemented — no commit ever introduced the API
git log --all -S "api_name" -- "*.rs" "*.py" "*.lua" "*.ts"
# → No results means the API was never coded

# Case B: Was removed — a deletion commit removed it
git log --all --diff-filter=D -S "api_name"
# → If found, examine the old implementation:
git show <delete_commit>^:path/to/file | head -200

# Case C: Spec-only — exists only in .md/.spec files
git log --all -S "api_name" -- "*.md" "*.spec"
# → Results only in specification files confirms "spec-only"
```

### 3. Identify the Specific Specification Section

Once you find the API in a spec document, identify:

- Section number and heading
- What the spec says about path resolution, defaults, behavior
- Any "design decisions" or "confirmed" annotations nearby
- Cross-references to other sections (platform paths, config directories)

### 4. Trace Spec Evolution via Git History

The spec document's git history may reveal design intent:

```bash
# Find commits that modified the API's spec definition
git log --all --oneline -S "api_name" -- "SPECIFICATION.md"

# See what the spec said before a particular change
git show <commit> -- SPECIFICATION.md | grep -B5 -A5 "api_name"
```

Key patterns to watch for:

- **Removal of baseline definition:** A commit that deletes "based on X" or "relative to Y" is an intentional design decision to leave the question open.
- **Tilde/absolute path examples commented out:** Signals the spec writer deferred a decision.
- **Platform path changes:** A commit adding platform directory tables (XDG/Win) may interact with path resolution design.

### 5. Classify the Compatibility Surface

| Finding | Implication |
| --------- | ------------- |
| Spec-only, no code in any fork | **Zero backward-compat constraints.** Pure design decision. Freely choose semantics. |
| Previously existed, then removed | Restoring changes contract. Check original behavior via `git show <parent>^:path`. |
| Spec says "relative + absolute" but no base defined | Design deliberately left open. The recent platform-path change likely removed the base reference on purpose. |

### 6. Report Structure for PM Questions

When reporting to a PM or design lead, structure the findings as:

1. **Presence Map** — which repos have it in code vs spec vs neither
2. **Spec Definition** — exact wording from the spec document (with section reference)
3. **Evolution History** — what changed in recent commits (especially any deletion of the base definition)
4. **Compatibility Constraint** — almost always "zero" for spec-only APIs
5. **Recommended Base** — backed by rationale (Neovim `:source` compatibility, user intuition, etc.)

## Pitfalls

**Spec-is-not-code:** An API comprehensively defined in a spec with examples, tables, and error handling may still have zero lines of implementation. Spec detail does not imply implementation existence.

**Commented-out spec examples:** Spec writers often comment out examples they are unsure about (prefixed with `#` in Python, `--` in Lua). These are weaker signals than active examples.

**Platform path commits:** A commit that reorganizes platform directory definitions (XDG → table format) may have deliberately removed a relative-path baseline. Check the diff, not just the final state.

**Worktree divergence:** The spec in `.worktree/<branch>/SPECIFICATION.md` may differ from the root spec. The branch-specific version is the authoritative version for that branch's design decisions.

## Reference

See `api-compatibility-investigation` for the general cross-fork API investigation workflow. See `specification-audit` for specification document quality checks.

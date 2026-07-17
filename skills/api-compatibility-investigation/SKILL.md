---
name: api-compatibility-investigation
description: "Investigate API compatibility, feature origin, and value acceptance across a fork chain or related codebase hierarchy. Covers fork discovery, parallel search, git history tracing, and compatibility classification."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [git, fork, api-compat, investigation, ghq]
    related_skills: [git-workflow]
---

# API Compatibility Investigation

Investigate whether an API (function, class, method, config value) exists across a fork chain or related project hierarchy, and whether its signature/values are compatible.

## When to Use

- User reports a feature missing or behaving differently across forks
- You need to know if a function existed upstream before modifying it
- You need to determine the canonical set of accepted values for a parameter
- Porting a feature between repos and need to know the original contract

## Procedure

### 1. Discover the Fork Chain

```bash
# Find immediate parent
gh repo view owner/repo --json parent,isFork

# Recursively follow parent until isFork=false or parent=null
```

Document every repo in the chain: its URL, whether it's a fork, and its parent.

### 2. Clone All Repos Independently

Use ghq for cloning. Verify they exist:

```bash
ghq list | grep -i <project-keyword>
```

Each repo gets its own directory under `~/ghq/github.com/<owner>/<repo>/`. Never nest forks inside each other's worktrees.

### 3. Search All Repos in Parallel

For Python projects, search function definitions across all forks simultaneously:

```
search_files(pattern="def <function_name>", path=~/ghq/github.com/*/<project-glob>*/)
```

For other languages, adjust the pattern (e.g., `fn <name>`, `function <name>`, `<name>(`).

**What you're looking for:**

- Does the function exist in each fork? → presence map
- What are the type hints / parameter names? → signature divergence
- What Literal values are accepted? → value set divergence

### 4. Trace Feature Origin

On the repo that has the feature, trace when it was introduced:

```bash
# Search content changes (function introduction)
git log --oneline --all -S "def function_name" -- <relative-file-path>

# Search commit messages
git log --oneline --all --grep="keyword" -- <relative-file-path>
```

This distinguishes "added by this fork" from "existed upstream."

### 5. Compare Implementations

Read the relevant source files from each fork's default branch. Note:

| Dimension | What to check |
| ----------- | --------------- |
| Type hints | Literal values, Optional wrappers, union types |
| Defaults | Config file defaults vs function defaults |
| Case sensitivity | Does the implementation normalize input (`.lower()`, `.upper()`)? |
| Behavior | What OpenCV/API values map to what internal state? |

### 6. Classify the API Surface

Categorize the findings to guide the recommendation:

| Finding | Implication |
| --------- | ------------- |
| In current fork only | Fork-specific addition. Safe to change without cross-fork compat concern. |
| In all forks with same signature | Upstream-origin API. Must maintain backward compat across entire chain. |
| In all forks with different signatures | Risk of silent breakage if scripts migrate between forks. Needs compat layer or alignment. |
| In upstream but removed in fork | Known upstream contract that was intentionally changed. Document the divergence. |

### 7. Check for Users of the API

Before making any recommendation, verify none of the sample scripts, tests, or user-facing examples use the API across any fork:

```
search_files(pattern="<function_name>|<config_key>", path=<each-repo-path>, file_glob="*.py")
```

Silent usage in uninspected scripts is the highest-risk compatibility gap.

## Pitfalls

**Silent vs. absent:** Zero grep results in upstream repos means the feature was never there, not that it was removed. Always check `git log -S` for the original introduction commit to be sure.

**Half-chain cloning:** You may have only the current fork cloned. If `gh repo view --json parent` reveals a parent not in your ghq list, clone it and continue.

**Non-linear fork chains:** A repo may be a fork of a different project entirely (e.g., a feature fork vs a maintenance fork of the same root). Verify the actual parent relationship rather than assuming a linear chain.

**Case-insensitive implementation:** If `value.lower()` is used internally, the code accepts any casing, but config files and UI values may use a specific canonical form. Use the config/UI form for type hints and documentation,

## Reference

See `git-workflow` skill for worktree management, cloning conventions, and PR workflow.

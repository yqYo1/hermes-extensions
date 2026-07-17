---
name: fork-chain-baseline-pinning
description: "Establish immutable commit baselines for script compatibility across a fork chain. Covers unpinned branch reference detection in specs, deletion-commit fork-point analysis, remote state verification, and producing a pinned baseline table with repo URL + branch + SHA."
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [git, fork, baseline, compatibility, spec]
    related_skills: [api-compatibility-investigation, specification-audit]
---

# Fork Chain Baseline Pinning

Resolve time-dependent branch-name references in specification documents to immutable commit SHAs across a fork chain, establishing precise baselines for script compatibility verification.

## When to Use

- A SPECIFICATION.md (or similar document) references "メインブランチ" / "デフォルトブランチ" / "fork元" without pinned commits
- You need to determine "which version of each fork is the compatibility reference" before discussing design changes
- A compatibility section (e.g., §4.6 of a spec) says "互換性確認の対象は…" but doesn't pin the actual commits
- You need to check whether a deletion commit on a refactor branch affects the default branch

## Procedure

### 1. Extract the Fork Chain from the Spec

Read the spec section that defines compatibility scope. Typical phrasing:
- "現在のフォークのメインブランチ"
- "フォーク元である Extension のデフォルトブランチ"
- "Extension の fork 元である modified のデフォルトブランチ"

Derive repo URLs from:
- The current repo's `git remote get-url origin`
- `gh repo view owner/repo --json parent,isFork`
- Recursive parent traversal until `isFork=false`

If repo URLs are absent from the spec, note this as a spec gap.

### 2. Clone and Verify Each Repo

```bash
ghq get https://github.com/<owner>/<repo>.git
cd ~/ghq/github.com/<owner>/<repo>
```

For each repo, run in parallel:

```bash
# Default branch name
git symbolic-ref refs/remotes/origin/HEAD | sed 's|refs/remotes/origin/||'

# Current HEAD
git rev-parse HEAD

# Remote verification
git ls-remote origin refs/heads/<default-branch>

# Tags (alternative pinning points)
git tag --sort=-creatordate | head -10

# Remote branches
git ls-remote --heads origin | head -20

# First commit (to verify shared root across chain)
git log --oneline --reverse | head -1

# Recent history
git log --oneline -20 --all
```

### 3. Fork-Point and Deletion Analysis

If the current repo has a working branch (e.g., `refactor/rust-core`) with a deletion commit:

```bash
# Fork point between main and refactor branch
git merge-base main refactor/rust-core

# Does main contain the deletion commit?
git branch --contains 3717027

# Does the deletion commit's parent exist on main?
git merge-base --is-ancestor 3717027^1 main

# Is main an ancestor of refactor branch?
git merge-base --is-ancestor main refactor/rust-core
```

**Classification table:**

| Pattern | Baseline choice |
|---------|----------------|
| Deletion on refactor branch only, not on main | `main` HEAD = pre-refactor baseline |
| Deletion's first parent also only on refactor | `main` HEAD is the correct snapshot; deletion parent is NOT the fork point |
| Fork point = `main` HEAD | `main` hasn't moved since branch was created |
| `main` IS ancestor of refactor | refactor branch is pure superset of main |

### 4. Produce the Baseline Report

Generate a table:

```markdown
| # | リポジトリ URL | 役割 | デフォルトブランチ | ベースライン SHA | リモート検証 |
|---|---|---|---|---|---|
| 1 | `https://github.com/...` | 現行フォーク | `main` | `<full-sha>` | ローカル=リモート一致 |
| 2 | `https://github.com/...` | フォーク元(Extension) | `master` | `<full-sha>` | ローカル=リモート一致 |
| 3 | `https://github.com/...` | 元祖(Modified) | `master` | `<full-sha>` | ローカル=リモート一致 |
```

Add deletion-commit relationship notes:

| 項目 | 値 |
|------|-----|
| 削除コミット | `<sha>` ("message") |
| 第一親 | `<parent-sha>` |
| マージコミット? | Yes/No |
| 所属ブランチ | `<branch>`のみ / `main`にも存在 |
| 分岐点 | `<sha>` |

### 5. Recommend Spec Fixes

Identify spec sections with unpinned references:

| セクション | 現状 | 推奨改定 |
|-----------|------|---------|
| §4.6 | ブランチ名のみ | ベースライン表に置き換え |
| §10.7 | ベースライン未参照 | §4.6への参照追加 |
| §1.2 | 間接参照のみ | ベースライン表への直接リンク追加 |

**Recommended immutable baseline scheme:** `{repo_url}#{branch}:{sha}`

**Policy statement to include:** "Default branch movement does NOT automatically extend the baseline scope. Only deliberate spec updates change pinned baselines."

## Pitfalls

**SHA alone is insufficient:** The same SHA could theoretically exist in different repos. Always pair with repo URL.

**Branch names are time-dependent:** The "main branch" at spec-writing time may differ from the "main branch" at implementation time. Always pin the actual SHA.

**Deletion commits on refactor branches ≠ main state:** A `refactor: remove existing implementation` commit on a working branch does not affect the default branch. Verify the branch relationship before concluding the baseline is wrong.

**Don't forget remote verification:** If the remote default branch moved since your local clone, your baseline is stale. Always verify `git ls-remote` matches local.

**Tags before default branches:** If the spec references a release version and the tag exists, prefer the tag over the default branch HEAD.

**Common root check:** All forks in a chain should share the same initial commit. If they don't, the fork relationship may be non-linear or the repos may not be true forks.

## References

- `api-compatibility-investigation` skill — broader fork-chain API investigation that follows baseline pinning
- `specification-audit` skill — spec audit patterns for detecting unpinned references
- `git-workflow` skill — worktree management, cloning conventions

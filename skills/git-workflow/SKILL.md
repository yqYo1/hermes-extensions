---
name: git-workflow
description: "Git workflow: ghq + worktree mode, branch management, and PR conventions."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [git, ghq, worktree, workflow]
    related_skills: [host-environment, github-repo-management]
---

# Git Workflow

## Repository Management

### Clone
- Use `ghq` at `~/.nix-profile/bin/ghq` for cloning repositories.

### Default Branch Protection
- For each repository under `ghq`, the **root directory must always remain on the remote default branch** (main, develop, etc.).
- The root directory is a **mirror of the remote default branch** — it should reflect exactly what is on the remote, with no local modifications.
- On the default branch, **only pull from the remote** — never commit, push, or make any local changes.
- **CRITICAL**: If you find yourself working on a feature branch in the root directory, **stop immediately**, checkout the default branch, and move work to a worktree. This is a workflow violation.

### Worktree Mode
- Perform **all work exclusively** in `.worktree/<branch>/` directories.
- When `delegate_task` changes files, branch off the parent worktree.
- **Never create or check out feature branches in the root directory.**
- **NEVER run `git checkout` inside a worktree to switch branches.** A worktree is bound to a single branch; switching branches inside it violates the worktree contract and causes confusion. If you need to work on a different branch, create a **new worktree** instead.
- **Principle: Create a new worktree rather than switching branches.** Whether in the root directory or inside an existing worktree, always prefer `git worktree add` over `git checkout` for starting work on a new branch.

## Fork Handling

When working with forks on GitHub (or other remotes):

- **Clone the fork independently using `ghq`**, not as a worktree of the upstream repository.
- The fork and upstream are separate repositories with separate remotes. Treat them as independent clones.
- Example:
  ```bash
  # Clone upstream (for reference, read-only)
  ghq get github.com/original-owner/original-repo

  # Clone your fork (for your work, read-write)
  ghq get github.com/your-username/forked-repo
  ```
- Each clone has its own `.git/` directory, its own remotes, and its own worktrees.
- **Never nest a fork inside another repository's worktree.** This creates confusion about which remote to push to and which branch belongs to which repo.

## Pull Requests

- For PRs in **your repositories**, target `your-username/<repo>` (not upstream).
- Ensure the remote is SSH: `git@github.com:your-username/...`.

## Merging Changes to Default Branch

When you need to apply changes to the default branch (e.g., main):

1. **Do NOT commit directly to the default branch locally.**
2. **Create a feature branch in a worktree**, do your work there, and push the branch to the remote.
3. **Open a Pull Request (or Merge Request)** on the remote (GitHub, GitLab, etc.).
4. **Merge the PR on the remote** using the web UI or API.
5. **Pull the updated default branch locally** to sync your root directory:
   ```bash
   cd /path/to/repo/root
   git pull origin main
   ```

This ensures:
- The default branch on the remote is the single source of truth.
- Local root directory remains a clean mirror of the remote default branch.
- All changes go through review (if PR review is enabled) before hitting the default branch.

## Git Identity Configuration

### Critical: No Local User Settings in Worktrees

- **NEVER set `user.name` or `user.email` in local `.git/config` within worktrees.**
- Local git identity settings override global settings and can cause commits to be authored under wrong identities (e.g., "PokeCon Dev" instead of the user's GitHub account).
- If local `user.name` or `user.email` exists in a worktree, **remove them immediately**:
  ```bash
  git config --local --unset user.name
  git config --local --unset user.email
  ```
- Always rely on **global `~/.gitconfig`** for identity settings.
- Before making any commit in a worktree, verify identity:
  ```bash
  git config --local user.name 2>/dev/null || git config --global user.name
  git config --local user.email 2>/dev/null || git config --global user.email
  ```

### Detecting and Fixing Wrong Commit Author

If commits show the wrong author (e.g., "PokeCon Dev" instead of the user's GitHub account), the cause is almost always a local `user.name`/`user.email` override in the worktree.

**Detection:**
```bash
git log --oneline --author="Wrong Name" --format="%h %an <%ae> %s"
```

**Fix for unpushed commits:**
```bash
git commit --amend --author="Correct Name <correct@email.com>" --no-edit
```

**Fix for already-pushed commits (requires force push):**
```bash
git filter-branch --env-filter '
if [ "$GIT_AUTHOR_NAME" = "Wrong Name" ]; then
    export GIT_AUTHOR_NAME="Correct Name"
    export GIT_AUTHOR_EMAIL="correct@email.com"
fi
if [ "$GIT_COMMITTER_NAME" = "Wrong Name" ]; then
    export GIT_COMMITTER_NAME="Correct Name"
    export GIT_COMMITTER_EMAIL="correct@email.com"
fi
' --force -- --all

git push --force --all origin
```

**Prevention (run in every new worktree):**
```bash
git config --local --unset user.name 2>/dev/null || true
git config --local --unset user.email 2>/dev/null || true
```

- **Do NOT create or modify any local `.git/config` settings unless absolutely necessary.**
- The global `~/.gitconfig` is already configured with the user's identity and preferences. There is no need to duplicate or override these in worktrees.
- Only override local settings when there is a specific technical requirement (e.g., repository-specific hooks, worktree-specific paths). Identity settings are never a valid reason for local overrides.
- If you find yourself wanting to set a local git config value, **stop and ask whether it is truly necessary**. In most cases, the answer is no.

## Subagent Branch Cleanup

### Problem

`delegate_task` subagents may create numerous temporary branches and worktrees (e.g., `phase4-*`, `phase5-*`, `phase6-*`) for parallel work. These accumulate and clutter both local and remote repositories.

### Prevention

- When spawning subagents for parallel work, **instruct them to use a single branch naming convention** or consolidate work into fewer branches.
- Prefer **sequential work on a single branch** over many parallel temporary branches unless parallelism is explicitly required.

### Cleanup Procedure

After subagent work completes, audit and remove temporary branches:

```bash
# List all local branches (excluding main/default)
git branch | grep -v "main\|develop"

# List all remote branches
git branch -r

# Delete remote temporary branches
git push origin --delete <temp-branch-1> <temp-branch-2> ...

# Remove local worktrees (must remove worktree before deleting branch)
git worktree remove <worktree-path>          # if clean
git worktree remove --force <worktree-path>  # if dirty

# Delete local branches
git branch -D <temp-branch-1> <temp-branch-2> ...
```

### What to Keep

- The user's main working branch (e.g., `refactor/rust-core`)
- Branches with open PRs
- Branches explicitly requested by the user
- The current active worktree

### What to Delete

- `phase*-*` pattern branches created by subagents
- Detached HEAD worktrees
- Branches already merged to main
- Any branch not referenced in an open PR and not actively being worked on

## Worktree Path Convention

- `git worktree add` automatically sanitizes branch names for filesystem safety.
- **Slashes in branch names become hyphens in directory names.**
  - Branch `refactor/rust-core` → Worktree `.worktree/refactor-rust-core/`
  - Branch `feature/new-ui` → Worktree `.worktree/feature-new-ui/`
- Always verify the actual worktree path with `git worktree list` before running commands.
- **Each worktree is bound to exactly one branch.** Do not attempt to switch branches inside a worktree with `git checkout` — this leaves the worktree in an inconsistent state. Always create a new worktree for new branch work.

### Finding the Actual Worktree Path

The `.git` file in a worktree directory contains a `gitdir:` pointer. If `git status` fails with "not a git repository", you may be in a symlinked or copied path rather than the actual worktree:

```bash
# List all worktrees with their actual paths
git worktree list

# The actual worktree path may differ from the expected path.
# For example, if ghq root is ~/ghq/github.com/your-username/repo,
# the worktree for branch refactor/rust-core is at:
# ~/ghq/github.com/your-username/repo/.worktree/refactor-rust-core/
# NOT at ~/repo/.worktree/refactor-rust-core/
```

**Always use `git worktree list` to verify the actual path before operations.**

### Duplicate File Path Pitfall

When using `ghq` with git worktrees, the same file may exist at two different paths:

- `~/ghq/github.com/<user>/<repo>/.worktree/<branch>/<file>` (the actual git worktree)
- `~/<repo>/.worktree/<branch>/<file>` (a stale copy or symlink target, NOT git-tracked)

**Symptom:** `patch` appears to succeed but `git diff` shows no changes. The file size differs between the two paths.

**Detection:**

```bash
# Compare file sizes
ls -la ~/ghq/.../.worktree/<branch>/FILE
ls -la ~/<repo>/.worktree/<branch>/FILE

# Compare hashes
md5sum ~/ghq/.../.worktree/<branch>/FILE
md5sum ~/<repo>/.worktree/<branch>/FILE
```

**Fix:** Always use the path under `~/ghq/` for git operations. The `~/<repo>/` path may be a stale copy that is not tracked by git.

**Prevention:** Before any file modification, verify the file is in a git-tracked directory:

```bash
cd $(dirname FILE) && git rev-parse --git-dir
```

## Automatic Commit & Push

- **Commit and push automatically at natural work boundaries** without waiting for explicit user instruction.
- A "work boundary" is any of: task completion, file deletion, significant change set, phase transition, or before switching contexts.
- **All commit messages MUST be in English following Conventional Commits format.** Never write commit messages in Japanese or as Japanese sentences.
- Use descriptive commit messages. Run `nix fmt` before committing if the project uses nix formatting.
- If push is rejected (non-fast-forward), pull with rebase first, then push again.
- **User explicitly requires frequent commits/pushes** — do not wait for user to say "commit now". Treat commit/push as part of the workflow, not a separate action requiring permission.
- If push is rejected (non-fast-forward), pull with rebase first, then push again.

### Commit Frequency Guidelines

| Scenario | Action |
| ---------- | -------- |
| Single file fix (e.g., typo, one-line change) | Commit immediately after patch |
| Multiple related fixes in same file | Commit after all related patches |
| Cross-file changes for one feature | One commit for the feature |
| grill-me item resolution | Commit after each item's fix |
| Review feedback addressed | Commit per feedback item |
| Before switching to different task | Commit and push first |
| Before ending session | Final commit and push |

**Anti-pattern to avoid**: Making multiple patches across multiple files and leaving them uncommitted. The user explicitly called this out as a workflow failure.

**Real-world pitfall from 2026-06-05 session**: Even with this skill loaded, the agent accumulated multiple fixes (shortcut button keybinding, holdEndSkip browser note, widget_mode type clarification, execution control key relationship) across multiple turns without committing. User had to explicitly remind: "変更したらある程度の単位毎に必ずコミットとpushを行って下さい" (Commit and push at every reasonable unit of change). **Lesson**: Do not wait for "completion" of a logical group — commit after EACH patch, especially during specification review/fix cycles where multiple independent fixes are made in sequence.

### Locating the Correct Worktree

When the current directory is not a git repository (e.g., `~/.hermes/hermes-agent`), locate the active worktree:

1. Find the repository with `ghq list | grep -i <project-name>`
2. Determine the worktree path: branch slashes become hyphens
   - Branch `refactor/rust-core` → `.worktree/refactor-rust-core/`
3. Verify with `git -C <worktree-path> status`
4. Always operate from the worktree directory, never from the root

## Workflow Summary

```
ghq get <repo>              # Clone to ~/ghq/github.com/...
cd <repo>                   # Root stays on default branch

# Need to work on a new branch? ALWAYS create a new worktree.
# NEVER use git checkout to switch branches, even inside a worktree.
git worktree add .worktree/<branch> <base-branch>
cd .worktree/<branch>       # All work happens here (slashes → hyphens!)

# Verify no local identity override
git config --local --unset user.name 2>/dev/null || true
git config --local --unset user.email 2>/dev/null || true

# ... make changes ...
git add -A && git commit -m "..." && git push
# ↑ Do this automatically at work boundaries, not just on explicit request

# Need another branch? Create another worktree — never git checkout.
git worktree add .worktree/<another-branch> <base-branch>
```

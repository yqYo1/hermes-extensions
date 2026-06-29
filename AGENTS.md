# AGENTS.md

## Session Directives (Auto-captured)

- [2026-06-15] nix-first workflow
- [2026-06-15] pytest for testing
- [2026-06-15] type hints required

## Formatting and Linting Tools

This project uses nix flake with treefmt-nix for formatting and nix flake check for linting.

### Current Tools

| File Type | Formatter | Linter |
| ----------- | ----------- | -------- |
| Nix | nixfmt | statix, deadnix |
| Python | ruff-format | ruff-check, basedpyright, ty |
| YAML | yamlfmt | yamllint, actionlint |
| Markdown | kakehashi (code blocks only) | markdownlint, textlint |
| General | - | typos |

### Tool Details

- **nixfmt**: Nix formatter (NixOS RFC standardization in progress)
- **ruff-format**: Python formatter (Rust-based, fast)
- **yamlfmt**: YAML formatter
- **kakehashi**: Markdown code block formatter (Tree-sitter based)
- **statix**: Nix linter (antipattern detection)
- **deadnix**: Nix linter (unused code detection)
- **ruff-check**: Python linter
- **basedpyright**: Python type checker (strict)
- **ty**: Python type checker (experimental, allowed to fail in CI)
- **yamllint**: YAML syntax checker
- **actionlint**: GitHub Actions YAML linter
- **markdownlint**: Markdown linter
- **textlint**: Text linter (Japanese/English prose)
- **typos**: Spell checker

### CI Configuration

- Format check: `nix fmt -- --fail-on-change --no-cache`
- Lint checks: `nix build .#checks.x86_64-linux.<check-name>`
- Experimental checks (ty): `continue-on-error: true`

### Future Tools to Add

When new file types are introduced, add the following tools:

| File Type | Formatter | Linter |
| ----------- | ----------- | -------- |
| TOML | taplo | taplo |
| JSON | jsonfmt | - |
| Shell | shfmt | shellcheck |
| Rust | rustfmt | clippy |
| Go | gofmt | golangci-lint |
| TypeScript/JavaScript | prettier | eslint |
| CSS/SCSS | prettier | stylelint |
| HTML | prettier | htmlhint |
| Docker | - | hadolint |
| Terraform | terraform fmt | tflint |

### Commands

```bash
# Format all files
nix fmt

# Check formatting
nix fmt -- --fail-on-change --no-cache

# Run all checks
nix flake check

# Run specific check
nix build .#checks.x86_64-linux.<check-name>

# Enter development shell
nix develop
```

## Skill Management

### Curator Eligibility

This repository's skills must NOT be marked as `created_by=agent` in `~/.hermes/skills/.usage.json`. Skills with this attribute become targets for the Hermes curator (auto-archive/consolidation).

**Why:** The curator treats `created_by=agent` as a signal that the skill was created by `skill_manage(action="create")` and is therefore eligible for automatic lifecycle management. Repository-managed skills should be exempt from this.

**Prevention:**

- Do NOT use `skill_manage(action="create")` for skills in this repository
- Edit skills directly via `patch` or `write_file` instead
- If `created_by=agent` is accidentally set, manually reset it to `null` in `.usage.json`

**Verification:**

```bash
python3 -c "import json; d=json.load(open('~/.hermes/skills/.usage.json')); print(d.get('git-workflow',{}).get('created_by')); print(d.get('subagent-policy',{}).get('created_by'))"
```

Expected output: `None` (not `"agent"`)

### Skill Language Policy

Skills in this repository MUST be written in **English** by default.

**Exception (near-mandatory):** Skills that deal with Japanese expression or writing conventions (e.g., textlint rules for Japanese prose, Japanese-specific writing style guidance) SHOULD be written in Japanese.
This is an obligation, not a permission — a skill about Japanese expression written in English would defeat its own purpose.

**Scope:** The policy applies to all user-facing content of a skill (description, body, examples). Code identifiers, command names, and tool names remain as-is regardless of language.

**Rationale:** English is the default working language for LLM-driven skill content; consistency across skills reduces cognitive load. Japanese-expression skills are the narrow exception because their content is inherently about Japanese.

### Skill Versioning Policy

Skill versions use [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

**Baseline:** The version on the `main` branch is the baseline. A PR bumps the version **once** based on the cumulative change in that PR, regardless of how many commits the PR contains.

**Which part to bump:**

| Change type | Bump | Examples |
| ----------- | ---- | -------- |
| Breaking change / loss of backward compatibility | MAJOR | Remove a documented section, rename the skill, change semantics |
| Backward-compatible feature addition / info addition | MINOR | Add a new section, add new config rows, complete previously-incomplete info |
| Bug fix / correction / formatting | PATCH | Correct wrong values, fix typos, wrap long lines |

**Procedure:**

1. Read the version currently on `main` (the baseline).
2. Classify the PR's net change against the table above.
3. Increment exactly one component by 1 (do not compound per-commit bumps).
4. Set the resulting version in the skill's frontmatter.

**Example:** If `main` has `1.0.0` and a PR both corrects wrong values (patch) and adds new config rows (minor), the PR publishes `1.1.0` — not `1.0.1` or `1.2.0`.

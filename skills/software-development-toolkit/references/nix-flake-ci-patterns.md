---
name: nix-flake-ci-patterns
description: "Common CI failure patterns and fixes for nix flake projects using treefmt, ruff, markdownlint, textlint, yamllint, actionlint, kakehashi, and basedpyright."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [nix, flake, ci, treefmt, ruff, markdownlint, textlint, yamllint, actionlint, kakehashi, basedpyright]
---

# Nix Flake CI Patterns

Common CI failure patterns and fixes for nix flake projects.

## treefmt-nix

### Problem: `settings.formatter.ruff.command` not defined

**Root cause:** treefmt-nix API changed. `config.treefmt.build.check` is now a function requiring `projectRoot` argument, not a derivation.

**Fix:** Remove explicit `formatting = config.treefmt.build.check;` from checks. The flake module auto-creates `checks.treefmt` and `formatter` outputs when `flakeCheck`/`flakeFormatter` are true (default).

```nix
# DON'T do this
formatting = config.treefmt.build.check;  # build.check is now a function

# DO this: let treefmt-nix auto-create the check
# (flakeCheck and flakeFormatter are true by default)
```

### Problem: `ruff` vs `ruff-format`

**Root cause:** treefmt-nix uses `ruff-format` as the formatter name, not `ruff`.

**Fix:** Use `ruff-format` in treefmt programs configuration.

```nix
treefmt = {
  programs = {
    ruff-format.enable = true;  # NOT ruff.enable
  };
};
```

## basedpyright

### Problem: `basedpyright-local` fails in nix sandbox

**Root cause:** basedpyright-local check tries to access local hermes-agent path that doesn't exist in CI.

**Fix:** Make the check gracefully skip when local hermes-agent is not found, and ensure `$out` is always created.

```nix
basedpyright-local = pkgs.stdenv.mkDerivation {
  name = "basedpyright-check-local";
  src = self;
  nativeBuildInputs = [ pkgs.basedpyright ];
  buildPhase = ''
    if [ -d "${self}/.hermes/hermes-agent" ]; then
      # ... run basedpyright ...
    else
      echo "Local hermes-agent not found, skipping local check"
    fi
    mkdir -p "$out"  # ALWAYS create $out
  '';
  installPhase = "mkdir -p $out";  # NOT "true"
};
```

### Problem: JSON parsing without python3 in sandbox

**Root cause:** basedpyright outputs JSON, but python3 may not be available in nix build sandbox.

**Fix:** Use `grep`/`cut` instead of python3 for JSON parsing.

```bash
# DON'T do this
ERRORS=$(python3 -c "import json; d=json.load(open('basedpyright-output.json')); print(d.get('summary',{}).get('errorCount',0))")

# DO this
ERRORS=$(grep -o '"errorCount":[0-9]*' basedpyright-output.json | cut -d: -f2)
```

## markdownlint

### Problem: MD013/line-length errors

**Root cause:** Default line length limit is 120 characters, but some content (URLs, code blocks) naturally exceeds this.

**Fix:** Create `.markdownlint.json` with relaxed line length setting.

```json
{
  "line-length": {
    "line_length": 250,
    "heading_line_length": 250,
    "code_block_line_length": 250,
    "tables": false
  }
}
```

### Problem: MD031/MD032 (blanks around fences/lists)

**Root cause:** Markdown files missing blank lines around code blocks and lists.

**Fix:** Add blank lines around code blocks and lists, or disable the rules if using a formatter that handles this automatically.

```json
{
  "MD031": false,
  "MD032": false
}
```

### Problem: MD060/table-column-style errors

**Root cause:** The markdownlint-cli v0.48.0 enforces strict table column style rules (MD060), which standard markdown parsers (GitHub, GitLab) don't require. Two styles exist:

| Style | Requirement | Example Header | Example Separator |
|-------|------------|----------------|-------------------|
| **compact** | Every pipe must have exactly one space on each side, **including the separator row** | `\| Field \| Required \|` | `\| --- \| --- \|` (spaces around dashes) |
| **aligned** | All rows (header, separator, data) must have pipes at the same column positions | `\| Field   \| Required \|` | `\|-------\|----------\|` (dash count matches header cell width) |

**Common failure modes:**

1. **Compact mode: separator has no spaces around pipes** — `|---|---|---|` triggers "missing space to the left/right" because dashes immediately touch the pipes. Fix: add spaces: `| --- | --- | --- |`.

2. **Aligned mode: separator dashes don't match header cell widths** — `| Field |` (8 chars between pipes) with `|-------|` (7 dashes) puts pipes at different positions. Fix: make dash count match the header cell content width exactly.

3. **Mixed style** — Header uses aligned-style padding but separator uses compact-style short dashes. This triggers both style checks.

**Preferred fix: Configure MD060 off in `.markdownlint.json`**

```json
{
  "MD060": false
}
```

This is the pragmatic solution when:
- Tables are valid GitHub-Flavored Markdown
- Standard markdown renderers display them correctly
- The table content has wide/irregular data cells that can't match header widths
- The project uses HTML/React/Vue components for rendering

**Alternative fix: Use aligned style consistently**

Match separator dash count to header cell width for every column:

```markdown
# Wrong: 9 dashes vs 8 chars " Field   " — pipes don't align
| Field   | Required |
|---------|----------|

# Correct: 8 dashes matches 8 chars
| Field   | Required |
|---------|----------|
```

To calculate: count the characters between the opening `|` and the next `|` in the header, including spaces. Use exactly that many dashes in the separator.

**Detection command:**
```bash
# Run markdownlint on specific files
nix run nixpkgs#markdownlint-cli -- path/to/file.md

# Run the CI check locally
nix build '.#checks.x86_64-linux.markdownlint'
```

**Warning:** When MD060 is active, fixing one table may expose MD060 errors in other tables in the same file. Disabling MD060 avoids cascading fixes.

## textlint

### Problem: "No rules found, textlint hasn't done anything"

**Root cause:** textlint requires at least one rule to function, but no `.textlintrc` exists and no rule packages are bundled.

**Fix:** Create `.textlintrc.json` with a basic rule or use `--rulesdir` with local rules.

```json
{
  "rules": {
    "no-todo": true
  }
}
```

Or create local rules and use `--rulesdir`:

```bash
textlint "**/*.md" --rulesdir textlint-rules/
```

## yamllint

### Problem: line-length errors in plugin.yaml files

**Root cause:** yamllint default line length is 80 characters, but plugin descriptions and other YAML content often exceeds this.

**Fix:** Create `.yamllint.yaml` with relaxed settings that align with yamlfmt output.

```yaml
extends: default
rules:
  line-length:
    max: 200
    allow-non-breakable-words: true
    allow-non-breakable-inline-mappings: true
  document-start: disable
```

### Problem: document-start warnings ("---")

**Root cause:** yamllint expects `---` at the start of YAML files, but yamlfmt removes it.

**Fix:** Disable `document-start` rule in `.yamllint.yaml`.

```yaml
rules:
  document-start: disable
```

## actionlint

### Problem: GitHub Actions YAML syntax errors

**Root cause:** actionlint detects syntax issues in `.github/workflows/*.yml`.

**Fix:** Run actionlint locally before pushing.

```bash
nix run nixpkgs#actionlint -- .github/workflows/*.yml
```

## kakehashi

### Problem: Markdown code block formatting issues

**Root cause:** kakehashi formats code blocks in markdown files, but may conflict with other formatters.

**Fix:** Ensure kakehashi is configured to use the same formatter as treefmt for code blocks.

```nix
kakehashi = pkgs.stdenv.mkDerivation {
  name = "kakehashi-check";
  src = self;
  nativeBuildInputs = [ kakehashi.packages.${system}.default ];
  buildPhase = ''
    kakehashi format --check --fail-on-change .
  '';
  installPhase = "mkdir -p $out";
};
```

## General CI Debugging Tips

### Check CI logs with gh CLI

```bash
# List recent runs
gh run list --branch <branch-name> --limit 5

# View specific run
gh run view <run-id>

# View failed logs
gh run view <run-id> --log-failed

# View specific job
gh run view <run-id> --job <job-id>
```

### Run checks locally before pushing

```bash
# Format check
nix fmt -- --fail-on-change --no-cache

# Specific check
nix build .#checks.x86_64-linux.<check-name>

# All checks
nix flake check
```

### Common check names

- `typos` — Spell checker
- `basedpyright-latest` — Type checker (latest hermes-agent)
- `basedpyright-local` — Type checker (local hermes-agent)
- `ty` — Experimental type checker
- `markdownlint` — Markdown linter
- `textlint` — Text linter
- `yamllint` — YAML linter
- `actionlint` — GitHub Actions linter
- `kakehashi` — Markdown code block formatter

## CI Workflow Configuration

### GitHub Actions workflow for nix flake CI

```yaml
name: CI

on:
  pull_request:
    branches: [main]

jobs:
  format:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: DeterminateSystems/nix-installer-action@main
      - run: nix fmt -- --fail-on-change --no-cache

  lint:
    runs-on: ubuntu-latest
    needs: format
    steps:
      - uses: actions/checkout@v4
      - uses: DeterminateSystems/nix-installer-action@main
      - run: nix build .#checks.x86_64-linux.typos
      - run: nix build .#checks.x86_64-linux.basedpyright-latest
      - run: nix build .#checks.x86_64-linux.basedpyright-local
      - run: nix build .#checks.x86_64-linux.ty
        continue-on-error: true
      - run: nix build .#checks.x86_64-linux.markdownlint
      - run: nix build .#checks.x86_64-linux.textlint
      - run: nix build .#checks.x86_64-linux.yamllint
      - run: nix build .#checks.x86_64-linux.actionlint
      - run: nix build .#checks.x86_64-linux.kakehashi
```

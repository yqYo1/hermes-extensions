---
name: append-only-spec-promotion
description: "Define and automate rolling append-only promotion of non-breaking additions to specification compatibility baselines. Layer 2 of the fork-chain baseline pinning model: gate checklists, corpus semantics, and automation requirements."
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [spec, compatibility, append-only, automation, gate]
    related_skills: [fork-chain-baseline-pinning, api-compatibility-investigation, specification-audit]
---

# Append-Only Spec Promotion (Layer 2)

Rolling append-only promotion mechanism for specification compatibility baselines. Layer 1 (immutable SHA pinning) captures the past; Layer 2 captures future non-breaking additions **without requiring manual spec edits for every upstream commit**.

## When to Use

- Executing the "recommend spec fixes" step from `fork-chain-baseline-pinning` and need to go beyond static pinning
- Writing §4.6-style compatibility sections that need both static baselines AND a future-proofing mechanism
- Implementing CI gates or a promotion bot that evaluates upstream commits for backwards compatibility
- Upgrading an existing "three repos listed by branch name" spec section to a formal two-layer policy

## Procedure

### 1. Confirm Layer 1 Baselines Are Pinned

Run the `fork-chain-baseline-pinning` skill first. Layer 2 requirements are **undefined** without three immutable SHAs. If the spec still says "メインブランチ" or "デフォルトブランチ", stop here and pin first.

### 2. Write the Rolling Policy Header

At §4.6 (or the spec's compatibility section), restructure into two numbered subsections:

```markdown
### 4.6 スクリプト互換性 — 不変ベースライン＋自動追補方式

> **要件**: 互換性は固定リファレンスコミットと自動追補保証の二層で保証する。スクリプトAPIに破壊的変更は加えない。
```

§4.6.1 = Layer 1 (immutable SHA table, from `fork-chain-baseline-pinning`)
§4.6.2 = Layer 2 (rolling policy, this skill)

### 3. Write the Gate Checklist

Every candidate commit on any monitored repo's default branch must pass ALL gates:

```markdown
| Gate | Description |
|------|-------------|
| **G1: Backward compat** | All user scripts within existing baselines (Layer 1) + previously promoted corpus must still load and run unchanged |
| **G2: Loadability** | Any new user scripts introduced by this commit must be loadable |
| **G3: No removal** | No public API function/class/module removed or renamed |
| **G4: No args removed** | No parameter removed or made required (was optional → still optional) |
| **G5: No narrowing** | No accepted type/value set narrowed; no default made more restrictive |
| **G6: No behavior change** | No silent semantic change (same call, different effect) |
| **G7: Added API OK** | New API, optional parameters, widened type/value constraints are **compatible** and OK |
| **G8: Dual test required** | Both runtime test AND API surface comparison (e.g., signature diff) required. Absence of sample scripts does NOT count as proof of compatibility |
| **G9: Full-chain re-eval** | When any one baseline advances, re-evaluate against all three repos |
```

### 4. Define Append-Only Corpus Semantics

```markdown
- Once a commit passes all gates, its scripts and API surface are added to the **append-only verified corpus**.
- A verified entry does NOT drop from the corpus if the upstream removes the script in a later commit.
- A commit that FAILS a gate does NOT promote. Existing state is preserved with diagnostics.
- Later commits are evaluated independently — a previously-failing commit does not block subsequent ones.
```

### 5. State Automation Requirements

```markdown
- "Automatic" means promotion does NOT require per-commit manual SPECIFICATION.md editing.
- Automation MUST NOT bypass branch protection, code review, or CI policy.
- The verified corpus and promotion state MUST be tracked with durable, machine-readable storage (manifest file, bot database, etc.).
- Implementation specifics (bot tooling, CI schedule, manifest format) are implementation details, but the tracking requirement is normative.
```

### 6. Update Spec Cross-References

The four spec sections that must reference the two-layer policy:

| Section | Original (dangerous) | After fix |
| --------- | --------------------- | ----------- |
| **§1.2** (design principles) | "§4.6を参照" | Link to both §4.6.1 and §4.6.2 explicitly |
| **§4.6** (compatibility itself) | Ambiguous branch names | Now the normative two-layer definition |
| **§10.2** (API design) | "リファクタリング前のスクリプト" vague | "不変ベースライン（§4.6.1）の全スクリプト" |
| **§10.7** (verification checklist) | Implementation status only | Full policy header + gate rows + old API rows |

### 7. Verify Cross-References

```bash
grep -n '§4\.' SPECIFICATION.md | grep -E '(§4\.6|§4\.6\.1|§4\.6\.2)'
```

- §1.2 must mention §4.6, §4.6.1, §4.6.2
- §10.2 must mention §4.6.1
- §10.7 must mention §4.6, §4.6.1, §4.6.2

## Pitfalls

**Layer 1 vs Layer 2 confusion:** Immutable baselines (Layer 1) are a static snapshot. Rolling promotion (Layer 2) is a dynamic process. Do not commingle the two. Layer 1 entries never change. Layer 2 entries are added but never removed.

**Automation is not bypass:** Writing "自動" in the spec does not override upstream branch protection or review policy. The gate checklist (G1–G9) must be satisfied in CI or a bot before promotion.

**Over-promising on new repos:** The three-chain model assumes a known fork hierarchy. For repos outside the known chain, Layer 2 monitoring is undefined — gate only on explicit inclusion.

**"Sample exists" ≠ proof:** A gate that says "sample scripts load OK" is insufficient without an API surface diff. G8 dual test requirement prevents false negatives.

**Rolling does not mean automatic for new language features:** A commit that adds a new API is compatible (G7 passes), but the implementation team must still build that API. Promotion is about the *contract* — implementation readiness is a separate concern.

## Example Changeset

Below is an example changeset showing how this skill was applied to a specification:

- `SPECIFICATION.md` §4.6: replaced 3-line branch-name compatibility with two-layer normative table + rolling policy
- `SPECIFICATION.md` §1.2: "§4.6を参照" → explicit two-layer reference
- `SPECIFICATION.md` §10.2: "リファクタリング前のスクリプト" → "不変ベースライン（§4.6.1）の全スクリプト"
- `SPECIFICATION.md` §10.7: implementation-status-only table → policy header + gate rows

## References

- `fork-chain-baseline-pinning` — prerequisite: Layer 1 SHA pinning procedure
- `api-compatibility-investigation` — broader fork-chain API compatibility analysis
- `specification-audit` — spec audit patterns for detecting unpinned references

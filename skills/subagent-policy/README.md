# Subagent-policy skill maintainer reference

This README documents the design rationale, upstream sources, and migration history for the subagent-policy skill. It is not loaded at runtime.

## Why 2.0.0

Version 2.0.0 is a major semantic shift from 1.x. Key changes:

| Change | 1.x | 2.0.0 |
| -------- | ----- | -------- |
| Guiding principle | "Delegate First, Execute Never" | "Use the right actor" |
| Direct execution | Last resort, discouraged on principle | Evaluated per task against explicit criteria |
| PM role | Planner/delegator only | Intent owner, outcome owner, planner, synthesizer, verifier |
| Prompt style | Verbose rules, explicit permissions, persistence language | Compact policy, outcome-first, no redundant guidance |
| Config values | Hardcoded in SKILL.md | Referenced as "inspect live config" |
| Primary token objective | Not explicit | Minimize main-agent context growth; total tokens are secondary |

The trigger for 2.0.0 is alignment with OpenAI's "Using GPT-5.6" guidance, which applies to Sol, and the revised PM role model.

## Official OpenAI guidance

The following sources informed this rewrite:

- **Model overview:** <https://developers.openai.com/api/docs/guides/latest-model> ("Using GPT-5.6" -- the current normative page)
- **Prompt guidance:** <https://developers.openai.com/api/docs/guides/prompt-guidance>
- **Prompting cookbook:** <https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide>
- **Announcement:** <https://openai.com/index/gpt-5-6/>

### Verified guidance applied

1. **Start minimal.** Begin with the smallest prompt and tool set that reliably completes the task; add guidance only for a demonstrated gap. (Rationale: long prompts can reduce benchmark scores and increase cost.)

2. **Avoid verbose rules.** Remove redundant instructions and examples. Hermes core system prompt already injects tool persistence, task completion, and parallel-call guidance; the skill should not duplicate that.

3. **No generic brevity instructions.** Do not say "be concise." Instead, lead with the conclusion/outcome and include required evidence and material caveats. Omit secondary detail and repetition.

4. **Compact autonomy policy.** Define autonomy once:
   - Answer/explain/review/diagnose/plan => inspect relevant material and report; do not implement unless asked.
   - Change/build/fix => make in-scope local changes and run relevant non-destructive validation without asking.
   - Require confirmation for external writes, destructive actions, purchases, or material scope expansion unless already explicitly authorized.

5. **Outcome-first prompts.** State goal, relevant context, constraints, required evidence, success criteria, and output format.

6. **Clean separation.** Break separable tasks into independent workstreams. Parallelize independent work, sequence dependencies, and synthesize results.

7. **No vague persistence language.** Avoid "be thorough" or repeated permission/persistence instructions. Hermes core handles tool persistence.

8. **Concise tool routing.** Tool descriptions and routing instructions should be explicit but brief.

### No dedicated Sol-specific prompt guide

OpenAI does not publish a separate "GPT-5.6 Sol prompting guide." The current normative page is "Using GPT-5.6" at the URL above, which states that GPT-5.5 prompt guidance remains applicable. Do not claim a dedicated guide exists.

## Main-agent token objective

The primary token objective is to reduce growth of the main agent's context, not necessarily to minimize aggregate tokens across all agents.

- Delegation keeps noisy intermediate tool output and exploration inside the child context; only a decision-complete final summary should return to the PM.
- Spending more total tokens is acceptable when it preserves PM reasoning capacity and required output quality.
- Do not remove required evidence, caveats, or validation to save tokens, and do not delegate tiny deterministic work when coordination overhead would be larger.

## Placement decisions: what goes where

| Concern | Location | Rationale |
| --------- | ---------- | ----------- |
| Task persistence, tool iteration, parallel calls | Hermes core system prompt | Injected before skills; skill duplicate would conflict and waste tokens |
| User identity, persona, high-level values | SOUL.md (user-managed) | Owned by the user, not by PM or subagent policy |
| PM/subagent role definition, delegation criteria, inheritance, blocked tools | SKILL.md (this skill) | Runtime decision-relevant; must be loaded per session |
| Config values (limits, timeouts) | `~/.hermes/config.yaml` | Change without skill updates; SKILL.md says to inspect live config |
| Design rationale, migration notes, source URLs | README.md | Not loaded at runtime; maintainer reference only |
| Task-specific rules for a delegation | `context` parameter on `delegate_task` | Varies per call; cannot be in a static skill |

## Migration from the old "Delegate First, Execute Never" framing

### What changed

The 1.x policy was built around a hard rule: "Do NOT edit files directly from the main agent when a subagent or coding agent could handle it."
This created friction for legitimate PM-owned work (writing PM-authored text, running short deterministic commands, orchestrating bounded tool chains) and incentivized wasteful delegation of trivial tasks.

The 2.0.0 policy replaces this with a balanced "use the right actor" framework that evaluates each unit of work on dimensions: output predictability, scope, PM-ownership, parallelizability, and context budget impact.

### What remains

- Subagents still do not inherit SOUL.md, memory, or project context (explicit `context` pass-through unchanged).
- The blocked-tools table and orchestrator/leaf distinction are preserved.
- Parent verification of external side effects is strengthened, not weakened.
- Protection bypass remains a hard failure.

### What was removed or shortened

- The entire "Coding Agent Delegation" section (5.7 in 1.5.0) is folded into the generic delegation criteria. External coding agents and `delegate_task` subagents follow the same "use the right actor" logic, while remaining distinct execution mechanisms.
- Input/Output Contracts (5.4) is collapsed into the Delegation Contract (section 4) without separate elaboration.
- Failure Modes and Countermeasures (5.5) is removed; the single critical rule (protection bypass = failure) moves to Verification (section 6). Other failure modes are generic and covered by Hermes core.
- Cost Optimization (5.6) is removed; cost-per-token guidance belongs in model/provider documentation, not delegation policy.
- Hardcoded config values are removed; replaced by a reference to live inspection.
- "Delegate First" language and the blockquote "When in doubt, delegate" are removed.

## Maintenance guidance

- **Add rules only after gaps are observed and evaluated.** Do not pre-emptively expand the policy to cover hypothetical failure modes. Each new rule must earn its token budget by preventing a demonstrated mistake.
- **When adding, prefer a compact rule over a verbose one.** Add evidence of the gap in README.md, not in SKILL.md.
- **If Hermes core system prompt changes**, review this skill for conflicts. The core prompt already handles task persistence; the skill should not duplicate that guidance.
- **Update version per AGENTS.md SemVer policy.** Changes that add criteria (backward-compatible) bump MINOR. Changes that remove or re-semantic documented behavior bump MAJOR. Fixes to values bump PATCH.

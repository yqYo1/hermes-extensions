"""
subagent-policy-injector — Injects sub-agent operation policy skills as
context into LLM calls via the pre_llm_call hook.

Purpose:
  When a session involves sub-agent work, this plugin automatically looks
  up the configured operation-policy skill names in ~/.hermes/skills/ and
  injects their contents so the LLM always has the correct operation policy
  instructions.

Configuration (config.yaml):
```yaml
plugins:
  subagent_policy_injector:
    enabled: true
    # One or more skill names to inject as operation policy.
    # These are looked up in ~/.hermes/skills/<category>/<name>/SKILL.md
    # or ~/.hermes/skills/<name>/SKILL.md.
    policy_skills:
      - subagent-driven-development
    # Template for the injection suffix.
    # {content} is replaced with the resolved skill content.
    suffix_template: |
      [sub-agent operation policy]
      Follow the operation policy described below:

      {content}
    # Only inject on the first turn of each session (default: true).
    inject_once: true
```
"""

from __future__ import annotations

import os
import threading
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_HERMES_HOME = os.environ.get(
    "HERMES_HOME",
    os.path.expanduser("~/.hermes"),
)
_SKILLS_DIR = os.path.join(_HERMES_HOME, "skills")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _cfg() -> dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        return load_config().get("plugins", {}).get("subagent_policy_injector", {})
    except Exception:
        return {}


def _enabled() -> bool:
    return _cfg().get("enabled", True)


def _policy_skills() -> list[str]:
    """Return configured policy skill names."""
    return _cfg().get("policy_skills", ["subagent-driven-development"])


def _suffix_template() -> str:
    """Return the injection suffix template."""
    return _cfg().get(
        "suffix_template",
        "[sub-agent operation policy]\n"
        "Follow the operation policy described below:\n\n{content}",
    )


def _inject_once() -> bool:
    return _cfg().get("inject_once", True)


# ---------------------------------------------------------------------------
# Session state (priming — inject only once per session)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_priming_done: set[str] = set()


def _mark_primed(session_id: str) -> None:
    with _lock:
        _priming_done.add(session_id)


def _is_primed(session_id: str) -> bool:
    with _lock:
        return session_id in _priming_done


def _clear_session(session_id: str) -> None:
    with _lock:
        _priming_done.discard(session_id)


# ---------------------------------------------------------------------------
# Skill resolver
# ---------------------------------------------------------------------------


def _load_skill(skill_name: str) -> Optional[str]:
    """Load SKILL.md content for a skill name from ~/.hermes/skills/.

    Tries:
      1. ~/.hermes/skills/<category>/<skill_name>/SKILL.md
      2. ~/.hermes/skills/<skill_name>/SKILL.md
    """
    if not skill_name or not os.path.isdir(_SKILLS_DIR):
        return None

    try:
        # With category (e.g. software-development/subagent-driven-development/SKILL.md)
        for category_dir in os.listdir(_SKILLS_DIR):
            skill_dir_path = os.path.join(_SKILLS_DIR, category_dir, skill_name)
            skill_md_path = os.path.join(skill_dir_path, "SKILL.md")
            if os.path.isfile(skill_md_path):
                with open(skill_md_path, encoding="utf-8") as f:
                    content = f.read()
                return content.strip()

        # Bare (e.g. subagent-driven-development/SKILL.md)
        bare_skill_path = os.path.join(_SKILLS_DIR, skill_name, "SKILL.md")
        if os.path.isfile(bare_skill_path):
            with open(bare_skill_path, encoding="utf-8") as f:
                content = f.read()
            return content.strip()

        print(
            f"[subagent-policy-injector] Skill '{skill_name}' not found in {_SKILLS_DIR}"
        )
        return None

    except (FileNotFoundError, IOError, OSError) as exc:
        print(f"[subagent-policy-injector] Failed to load skill '{skill_name}': {exc}")
        return None


def _load_policy_skills() -> list[tuple[str, str]]:
    """Load all configured policy skills.

    Returns a list of (skill_name, resolved_content) tuples.
    """
    results: list[tuple[str, str]] = []
    for name in _policy_skills():
        content = _load_skill(name)
        if content:
            results.append((name, content))
        else:
            print(
                f"[subagent-policy-injector] Policy skill '{name}' could not be loaded"
            )
    return results


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


def _on_pre_llm_call(
    session_id: str = "",
    is_first_turn: bool = False,
    **kwargs: Any,
) -> dict[str, str] | None:
    """pre_llm_call hook: inject sub-agent policy skill content."""
    if not _enabled():
        return None

    policy_skills = _policy_skills()
    if not policy_skills:
        return None

    # If inject_once is enabled and session already primed, skip
    if _inject_once() and _is_primed(session_id):
        return None

    loaded = _load_policy_skills()
    if not loaded:
        return None

    # Build suffix content
    parts: list[str] = []
    for name, content in loaded:
        parts.append(f"--- {name} ---\n{content}")

    merged_content = "\n\n".join(parts)
    template = _suffix_template()
    suffix = template.replace("{content}", merged_content)

    # Mark session as primed if inject_once is enabled
    if _inject_once():
        _mark_primed(session_id)

    return {"context": f"\n\n[plugin: subagent-policy-injector]\n{suffix}"}


# ---------------------------------------------------------------------------
# Session boundaries
# ---------------------------------------------------------------------------


def _on_session_end(session_id: str = "", **kwargs: Any) -> None:
    if session_id:
        _clear_session(session_id)


def _on_session_reset(session_id: str = "", **kwargs: Any) -> None:
    if session_id:
        _clear_session(session_id)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(ctx: Any) -> None:
    if not _enabled():
        print("[subagent-policy-injector] disabled in config.")
        return

    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_hook("on_session_reset", _on_session_reset)

    skills = _policy_skills()
    print(f"[subagent-policy-injector] registered (policy skills: {skills}).")

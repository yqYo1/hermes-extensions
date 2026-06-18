"""
prompt-injector — Injects configured context into every user message
via the pre_llm_call hook.

Sources:
  - **Static text** defined directly in config.yaml
  - **Files** read from the filesystem (e.g. AGENTS.md, notes, rules)
  - **Skills** loaded from ~/.hermes/skills/ (SKILL.md content)

Configuration (config.yaml):
```yaml
plugins:
  prompt_injector:
    enabled: true
    sources:
      - type: static
        key: "always-on-rules"
        label: "Always-On Rules"
        text: |
          IMPORTANT: Always verify file paths with git worktree list before editing.
          Always use ghq + worktree workflow.
        enabled: true

      - type: file
        key: "project-agents"
        label: "Project AGENTS.md"
        path: "/home/yayoi/ghq/github.com/yqYo1/hermes-extensions/AGENTS.md"
        enabled: false

      - type: skill
        key: "git-workflow-context"
        label: "Git Workflow Context"
        skill_name: "git-workflow"
        enabled: false

    # Designate one source as the "priming" source — injected only on the
    # first turn of each session. Others inject every turn.
    priming_source: "always-on-rules"
```
"""

from __future__ import annotations

import os
import threading
from typing import Any, Optional

# ---------------------------------------------------------------------------
# パス定数
# ---------------------------------------------------------------------------

_HERMES_HOME = os.environ.get(
    "HERMES_HOME",
    os.path.expanduser("~/.hermes"),
)
_SKILLS_DIR = os.path.join(_HERMES_HOME, "skills")

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------


def _cfg() -> dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        return load_config().get("plugins", {}).get("prompt_injector", {})
    except Exception:
        return {}


def _enabled() -> bool:
    return _cfg().get("enabled", True)


def _priming_source_key() -> Optional[str]:
    return _cfg().get("priming_source")


def _sources() -> list[dict[str, Any]]:
    return _cfg().get("sources", [])


# ---------------------------------------------------------------------------
# セッション状態
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
# ソース解決
# ---------------------------------------------------------------------------


def _resolve_static(source: dict[str, Any]) -> Optional[str]:
    """静的テキストソース"""
    text = source.get("text", "")
    if not text:
        return None
    return text.strip()


def _resolve_file(source: dict[str, Any]) -> Optional[str]:
    """ファイルソース — ファイルの内容を読み込む"""
    path = source.get("path", "")
    if not path:
        return None
    path = os.path.expanduser(path)
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read().strip()
        return content if content else None
    except (FileNotFoundError, IOError, OSError) as exc:
        print(f"[prompt-injector] Failed to read file '{path}': {exc}")
        return None


def _resolve_skill(source: dict[str, Any]) -> Optional[str]:
    """スキルソース — スキルディレクトリを検索して SKILL.md を読み込む"""
    skill_name = source.get("skill_name", "")
    if not skill_name:
        return None

    # スキルは ~/.hermes/skills/<category>/<skill_name>/SKILL.md の構造
    # または ~/.hermes/skills/<skill_name>/SKILL.md（カテゴリなし）
    if not os.path.isdir(_SKILLS_DIR):
        return None

    try:
        # カテゴリ付きで検索（例: github/git-workflow/SKILL.md）
        for category_dir in os.listdir(_SKILLS_DIR):
            skill_dir_path = os.path.join(_SKILLS_DIR, category_dir, skill_name)
            skill_md_path = os.path.join(skill_dir_path, "SKILL.md")
            if os.path.isfile(skill_md_path):
                with open(skill_md_path, encoding="utf-8") as f:
                    content = f.read()
                return content.strip()

        # カテゴリなしで検索（例: git-workflow/SKILL.md）
        bare_skill_path = os.path.join(_SKILLS_DIR, skill_name, "SKILL.md")
        if os.path.isfile(bare_skill_path):
            with open(bare_skill_path, encoding="utf-8") as f:
                content = f.read()
            return content.strip()

        print(f"[prompt-injector] Skill '{skill_name}' not found in {_SKILLS_DIR}")
        return None

    except (FileNotFoundError, IOError, OSError) as exc:
        print(f"[prompt-injector] Failed to load skill '{skill_name}': {exc}")
        return None


_RESOLVERS = {
    "static": _resolve_static,
    "file": _resolve_file,
    "skill": _resolve_skill,
}


def _resolve_source(source: dict[str, Any]) -> Optional[str]:
    """ソースの type に応じて内容を解決"""
    stype = source.get("type", "")
    resolver = _RESOLVERS.get(stype)
    if not resolver:
        print(f"[prompt-injector] Unknown source type: {stype}")
        return None
    return resolver(source)


# ---------------------------------------------------------------------------
# フック
# ---------------------------------------------------------------------------


def _on_pre_llm_call(
    session_id: str = "",
    is_first_turn: bool = False,
    **kwargs: Any,
) -> dict[str, str] | None:
    """pre_llm_call フック: 設定された全ソースを解決して context に注入"""
    if not _enabled():
        return None

    priming_key = _priming_source_key()
    sources = _sources()
    if not sources:
        return None

    resolved_parts: list[str] = []

    for source in sources:
        if not source.get("enabled", True):
            continue

        key = source.get("key", "")
        label = source.get("label", key)

        # プライミングソース: 初回ターンのみ注入
        if key == priming_key:
            if _is_primed(session_id):
                continue
        # 非プライミングソース: 毎ターン注入

        content = _resolve_source(source)
        if content:
            resolved_parts.append(f"[context: {label}]\n{content}")

    if not resolved_parts:
        return None

    # 初回ターンならプライミング済みとしてマーク
    if priming_key:
        _mark_primed(session_id)

    merged = "\n\n---\n\n".join(resolved_parts)
    return {"context": f"\n\n[plugin: prompt-injector]\n{merged}"}


# ---------------------------------------------------------------------------
# セッション境界
# ---------------------------------------------------------------------------


def _on_session_end(session_id: str = "", **kwargs: Any) -> None:
    if session_id:
        _clear_session(session_id)


def _on_session_reset(session_id: str = "", **kwargs: Any) -> None:
    if session_id:
        _clear_session(session_id)


# ---------------------------------------------------------------------------
# 登録
# ---------------------------------------------------------------------------


def register(ctx: Any) -> None:
    if not _enabled():
        print("[prompt-injector] disabled in config.")
        return

    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_hook("on_session_reset", _on_session_reset)

    print("[prompt-injector] registered (v1.0.0).")

"""Qwen Cloud Token Plan provider profile.

Separate from the standard ``alibaba`` (pay-as-you-go) and
``alibaba-coding-plan`` profiles because it hits a dedicated endpoint
(token-plan.ap-southeast-1.maas.aliyuncs.com) with a dedicated API key
tier (keys prefixed ``sk-sp-``).  Token Plan keys/base-URLs are completely
separate from other Qwen Cloud tiers and must be used together.

Thinking control differs per model family on Token Plan.  All three
families share ``enable_thinking`` (bool), but the effort knob and the
budget/preserve controls vary:

* **Qwen models** (qwen3.x): ``thinking_budget`` (int) controls depth;
  ``preserve_thinking`` (bool) carries reasoning across turns on supported
  models.
* **GLM models** (glm-5.2): ``reasoning_effort`` (top-level) selects one of
  ``none``/``minimal``/``low``/``medium``/``high``/``xhigh``/``max``.
* **DeepSeek models** (deepseek-v4-pro): ``reasoning_effort`` (top-level)
  with ``low``/``medium``/``high``/``xhigh``/``max`` (where ``low`` and
  ``medium`` behave like ``high``, and ``xhigh`` like ``max``).

Wire-format references (Qwen Cloud official docs):
  - Thinking: docs.qwencloud.com/developer-guides/text-generation/thinking
  - DeepSeek: docs.qwencloud.com/developer-guides/third-party-models/deepseek
  - GLM:      docs.qwencloud.com/developer-guides/third-party-models/glm
"""

from __future__ import annotations

import os
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

# -- Thinking budget defaults (Qwen family) -----------------------------------
#
# Default thinking_budget (max thinking tokens) per Hermes effort level.
# Users can override the budget for a specific level by setting the
# corresponding QWEN_TOKEN_PLAN_THINKING_BUDGET_<LEVEL> environment variable
# (e.g. QWEN_TOKEN_PLAN_THINKING_BUDGET_HIGH=49152).
#
# These defaults are conservative references inspired by Qwen Cloud model
# pages (Qwen3.7-Max max output thinking ~65K, DeepSeek-V4-Pro max output
# ~393K).  They are intentionally modest so a per-call budget does not
# consume the entire output window on smaller models.
_DEFAULT_THINKING_BUDGETS: dict[str, int] = {
    "minimal": 512,
    "low": 2048,
    "medium": 8192,
    "high": 32768,
    "xhigh": 65536,
    "max": 131072,
    "ultra": 262144,
}

# Qwen models that support preserve_thinking (carry reasoning_content across
# turns).  Source: Qwen Cloud thinking docs.
# Note: qwen3.6-flash is NOT in this list.
_PRESERVE_THINKING_MODELS: frozenset[str] = frozenset(
    {
        "qwen3.8-max-preview",
        "qwen3.7-max",
        "qwen3.7-plus",
    }
)

# Valid reasoning_effort values for GLM-5.2 on Qwen Cloud.
# Source: docs.qwencloud.com/developer-guides/third-party-models/glm
_GLM_VALID_EFFORTS: frozenset[str] = frozenset(
    {
        "none",
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
        "max",
    }
)

# Valid reasoning_effort values for DeepSeek-V4 on Qwen Cloud.
# Source: docs.qwencloud.com/developer-guides/third-party-models/deepseek
_DEEPSEEK_VALID_EFFORTS: frozenset[str] = frozenset(
    {
        "low",
        "medium",
        "high",
        "xhigh",
        "max",
    }
)

# Per official docs: "low and medium produce the same behavior as high.
# xhigh produces the same behavior as max."
_DEEPSEEK_EFFORT_MAP: dict[str, str] = {
    "minimal": "high",
    "low": "high",
    "medium": "high",
    "high": "high",
    "xhigh": "max",
    "max": "max",
    "ultra": "max",
}


# -- Helpers ------------------------------------------------------------------


def _resolve_budget(
    effort: str,
    env_prefix: str,
    defaults: dict[str, int],
) -> int | None:
    """Resolve a thinking_budget for *effort* with env-var override.

    Checks ``<env_prefix>_<LEVEL>`` first, then *defaults*.  Returns None
    if the effort level is unknown (let the server apply its default).
    """
    effort = effort.strip().lower()
    env_name = f"{env_prefix}_{effort.upper()}"
    env_val = os.environ.get(env_name)
    if env_val:
        try:
            return int(env_val)
        except ValueError:
            pass
    return defaults.get(effort)


def _model_family(model: str | None) -> str:
    """Classify a model ID into a Token Plan family: qwen|glm|deepseek|unknown."""
    m = (model or "").strip().lower()
    if not m:
        return "unknown"
    if m.startswith("qwen"):
        return "qwen"
    if m.startswith("glm"):
        return "glm"
    if m.startswith("deepseek"):
        return "deepseek"
    return "unknown"


# -- Profile ------------------------------------------------------------------


class QwenTokenPlanProfile(ProviderProfile):
    """Qwen Cloud Token Plan — per-family thinking/effort handling."""

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict[str, Any] | None = None,
        model: str | None = None,
        **context: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Map Hermes reasoning effort to per-family Qwen Cloud parameters.

        Returns ``(extra_body_additions, top_level_kwargs)``.
        """
        extra_body: dict[str, Any] = {}
        top_level: dict[str, Any] = {}

        if not isinstance(reasoning_config, dict):
            return extra_body, top_level

        enabled = reasoning_config.get("enabled", True)
        effort = (reasoning_config.get("effort") or "").strip().lower()

        # Disabled / none → enable_thinking=false for all families.
        if enabled is False or effort == "none":
            extra_body["enable_thinking"] = False
            return extra_body, top_level

        family = _model_family(model)

        if family == "qwen":
            self._apply_qwen(extra_body, effort, model)
        elif family == "glm":
            self._apply_glm(extra_body, top_level, effort)
        elif family == "deepseek":
            self._apply_deepseek(extra_body, top_level, effort)

        return extra_body, top_level

    @staticmethod
    def _apply_qwen(
        extra_body: dict[str, Any],
        effort: str,
        model: str | None,
    ) -> None:
        """Qwen family: enable_thinking + thinking_budget + preserve_thinking."""
        extra_body["enable_thinking"] = True
        if effort:
            budget = _resolve_budget(
                effort,
                "QWEN_TOKEN_PLAN_THINKING_BUDGET",
                _DEFAULT_THINKING_BUDGETS,
            )
            if budget is not None:
                extra_body["thinking_budget"] = budget
        model_lower = (model or "").strip().lower()
        if model_lower in _PRESERVE_THINKING_MODELS:
            extra_body["preserve_thinking"] = True

    @staticmethod
    def _apply_glm(
        extra_body: dict[str, Any],
        top_level: dict[str, Any],
        effort: str,
    ) -> None:
        """GLM family: enable_thinking + reasoning_effort (top-level).

        Qwen Cloud GLM supports the same 7-level hierarchy as Hermes
        (none/minimal/low/medium/high/xhigh/max).  Hermes ``ultra`` (not a
        valid GLM value) clamps to ``max``.
        """
        extra_body["enable_thinking"] = True
        if not effort:
            return
        mapped = "max" if effort == "ultra" else effort
        if mapped in _GLM_VALID_EFFORTS:
            top_level["reasoning_effort"] = mapped

    @staticmethod
    def _apply_deepseek(
        extra_body: dict[str, Any],
        top_level: dict[str, Any],
        effort: str,
    ) -> None:
        """DeepSeek family: enable_thinking + reasoning_effort (top-level).

        Official mapping: low/medium→high, xhigh→max.  reasoning_effort is
        sent as a top-level parameter.
        """
        extra_body["enable_thinking"] = True
        if effort:
            mapped = _DEEPSEEK_EFFORT_MAP.get(effort)
            if mapped and mapped in _DEEPSEEK_VALID_EFFORTS:
                top_level["reasoning_effort"] = mapped


# -- Registration -------------------------------------------------------------


qwen_token_plan = QwenTokenPlanProfile(
    name="qwen-token-plan",
    aliases=("qwen-token"),
    display_name="Qwen Cloud (Token Plan)",
    description="Qwen Cloud Token Plan — dedicated subscription tier (Personal/Team)",
    signup_url="https://www.qwencloud.com/pricing/token-plan",
    env_vars=("QWEN_TOKEN_PLAN_API_KEY", "QWEN_TOKEN_PLAN_BASE_URL"),
    base_url="https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
    auth_type="api_key",
    fallback_models=(
        "qwen3.8-max-preview",
        "qwen3.7-max",
        "qwen3.7-plus",
        "qwen3.6-flash",
        "glm-5.2",
        "deepseek-v4-pro",
    ),
    default_aux_model="qwen3.7-plus",
)

register_provider(qwen_token_plan)

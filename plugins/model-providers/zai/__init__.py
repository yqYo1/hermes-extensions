"""
Z.AI / GLM provider — Coding Plan override of the builtin ``zai`` provider.

OVERVIEW
--------
This plugin overrides Hermes' builtin ``zai`` model provider by registering with
the same name (``zai``).  Hermes discovery follows last-writer-wins: user plugins
in ``$HERMES_HOME/plugins/model-providers/zai/`` supersede the bundled provider of
the same name.

THREE FIXES OVER THE BUILTIN
-----------------------------
1. **Coding Plan base URL** — uses ``https://api.z.ai/api/coding/paas/v4`` instead
   of the standard ``https://api.z.ai/api/paas/v4`` (standard tier).
2. **OpenAI SDK User-Agent fingerprinting** — injects ``default_headers`` so the
   SDK sends a neutral ``User-Agent: hermes-agent/1.0`` instead of its default
   identifying headers.
3. **'Hermes Agent' prompt rejection** — the phrase ``Hermes Agent`` in messages
   triggers HTTP 429 / code 1305 ("temporarily overloaded") on Z.AI endpoints.
   :meth:`prepare_messages` replaces it with ``Assistant``.

REASONING LOGIC
---------------
The reasoning-effort and thinking toggle logic is inherited from the builtin
provider:

- GLM-4.5+ models support ``extra_body.thinking = {"type": "enabled"|"disabled"}``
  to control thinking mode.
- GLM-5.2 additionally accepts a native ``reasoning_effort`` knob (``high`` or
  ``max``) as a top-level parameter.
- Model-version gating prevents sending unsupported parameters to older models
  (e.g. ``glm-4-9b``).
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)

# -- Model-version helpers (copied from builtin zai provider) ----------------


_GLM_VERSION_RE = re.compile(r"^glm-(\d+)(?:\.(\d+))?")


def _model_supports_thinking(model: str | None) -> bool:
    """GLM thinking-capable model families: glm-4.5 and later."""
    m = (model or "").strip().lower()
    match = _GLM_VERSION_RE.match(m)
    if not match:
        return False
    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    return (major, minor) >= (4, 5)


def _is_glm_5_2(model: str | None) -> bool:
    """Detect GLM-5.2 across alias spellings."""
    m = (model or "").strip().lower()
    if not m:
        return False
    return any(token in m for token in ("glm-5.2", "glm-5-2", "glm-5p2"))


def _glm_5_2_reasoning_effort(reasoning_config: dict | None) -> str | None:
    """Map Hermes reasoning effort onto GLM-5.2's native ``high``/``max``.

    GLM-5.2 only supports two enabled effort levels. ``xhigh``/``max``/``ultra``
    request the top tier; everything else that is enabled requests ``high`` (its
    minimum thinking level). When reasoning is explicitly disabled, or no effort
    preference is supplied, the server default is left untouched.
    """
    if not isinstance(reasoning_config, dict):
        return None
    if reasoning_config.get("enabled") is False:
        return None

    effort = (reasoning_config.get("effort") or "").strip().lower()
    if not effort or effort == "none":
        return None

    if effort in {"xhigh", "max", "ultra"}:
        return "max"
    # low / medium / minimal / high all clamp to GLM-5.2's minimum: high.
    return "high"


# -- Hostname detection for prompt sanitization ------------------------------


_ZAI_HOSTNAMES = frozenset(
    {
        "api.z.ai",
        "open.bigmodel.cn",
        "z.ai",
        "bigmodel.cn",
    }
)


def _is_zai_hostname(hostname: str) -> bool:
    """Return True if *hostname* belongs to Z.AI / Zhipu AI.

    Matches exact hostnames in ``_ZAI_HOSTNAMES`` and any subdomain thereof.
    """
    hostname = hostname.strip().lower()
    if hostname in _ZAI_HOSTNAMES:
        return True
    for zai_host in _ZAI_HOSTNAMES:
        if hostname.endswith("." + zai_host):
            return True
    return False


# -- Profile -----------------------------------------------------------------


class ZaiProfile(ProviderProfile):
    """Z.AI / GLM — Coding Plan override with reasoning, headers, and prompt safety."""

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict | None = None,
        model: str | None = None,
        **context: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Map Hermes reasoning config to Z.AI wire format.

        - GLM-4.5+: ``extra_body.thinking`` on/off
        - GLM-5.2 only: ``reasoning_effort`` (``high``/``max``) at top level

        Model-version gating prevents sending unsupported parameters to older
        models such as ``glm-4-9b``.
        """
        extra_body: dict[str, Any] = {}
        top_level: dict[str, Any] = {}

        if not _model_supports_thinking(model) and not _is_glm_5_2(model):
            return extra_body, top_level

        # Only emit when the user expressed a preference; omitting the field
        # keeps the server default (enabled) exactly as before.
        if isinstance(reasoning_config, dict):
            enabled = reasoning_config.get("enabled") is not False
            extra_body["thinking"] = {"type": "enabled" if enabled else "disabled"}

        if _is_glm_5_2(model):
            effort = _glm_5_2_reasoning_effort(reasoning_config)
            if effort is not None:
                top_level["reasoning_effort"] = effort

        return extra_body, top_level

    def prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Replace 'Hermes Agent' with 'Assistant' when talking to Z.AI endpoints.

        The phrase 'Hermes Agent' in prompts triggers HTTP 429 / code 1305
        ("temporarily overloaded") on Z.AI endpoints.  This method sanitises
        messages for all Z.AI hostnames (``api.z.ai``, ``open.bigmodel.cn``, and
        their subdomains).
        """
        hostname = self.get_hostname()
        if not hostname or not _is_zai_hostname(hostname):
            return messages

        prepared = copy.deepcopy(messages)
        for msg in prepared:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if isinstance(content, str) and "Hermes Agent" in content:
                msg["content"] = content.replace("Hermes Agent", "Assistant")
            elif isinstance(content, list):
                for part in content:
                    if (
                        isinstance(part, dict)
                        and isinstance(part.get("text"), str)
                        and "Hermes Agent" in part["text"]
                    ):
                        part["text"] = part["text"].replace("Hermes Agent", "Assistant")
        return prepared


# -- Registration ------------------------------------------------------------

zai = ZaiProfile(
    name="zai",
    aliases=("glm", "z-ai", "z.ai", "zhipu"),
    env_vars=("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"),
    display_name="Z.AI (GLM) - Coding Plan",
    description="Z.AI / GLM — Zhipu AI models (Coding Plan override with prompt sanitization)",
    signup_url="https://z.ai/",
    fallback_models=(
        "glm-5.2",
        "glm-5",
        "glm-4-9b",
    ),
    base_url="https://api.z.ai/api/coding/paas/v4",
    default_aux_model="glm-4.5-flash",
    default_headers={"User-Agent": "hermes-agent/1.0"},
)

register_provider(zai)

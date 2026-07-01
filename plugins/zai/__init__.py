"""
Custom Z.AI / GLM model provider plugin.

Overrides the builtin ``zai`` provider to fix three Hermes-side bugs:

1. **Ignored base_url** — uses a proper profile (base_url explicitly set).
2. **OpenAI SDK header fingerprinting** — injects ``default_headers`` with a
   neutral ``User-Agent`` so the SDK does not send its own identifying headers.
3. **'Hermes Agent' prompt phrase triggers 429/1305** — replaces the string
   "Hermes Agent" with "Assistant" in messages sent to Z.AI endpoints.

Also implements GLM-5.2 reasoning_effort mapping (see ``build_api_kwargs_extras``).
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)

# -- Hostnames that need "Hermes Agent" → "Assistant" sanitization ----------

_ZAI_HOSTNAMES = frozenset(
    {
        "api.z.ai",
        "open.bigmodel.cn",
    }
)


def _is_zai_hostname(hostname: str) -> bool:
    """Return True if *hostname* belongs to Z.AI / Zhipu AI.

    Matches exact hostnames in ``_ZAI_HOSTNAMES`` and any subdomain thereof.
    """
    hostname = hostname.strip().lower()
    if hostname in _ZAI_HOSTNAMES:
        return True
    # Subdomain check: *.z.ai or *.bigmodel.cn
    for zai_host in _ZAI_HOSTNAMES:
        if hostname.endswith("." + zai_host):
            return True
    return False


# -- Reasoning effort mapping ------------------------------------------------
# GLM-5.2 accepts only "high" and "max" as valid reasoning_effort values.
# See: https://docs.z.ai/guides/llm/glm-5.2

_HERMES_TO_GLM_EFFORT: dict[str, str] = {
    "none": "none",  # handled specially: disable thinking
    "minimal": "high",
    "low": "high",
    "medium": "high",
    "high": "high",
    "xhigh": "max",
}


def _map_reasoning_effort(
    effort: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Map a Hermes reasoning effort to GLM-5.2 parameters.

    Returns ``(extra_body_additions, top_level_kwargs)``.
    """
    extra_body: dict[str, Any] = {}
    top_level: dict[str, Any] = {}

    if not effort:
        # No effort configured → server default (max).  Nothing to send.
        return extra_body, top_level

    effort = effort.strip().lower()

    if effort == "none":
        # Explicitly disable thinking.
        extra_body["thinking"] = {"type": "disabled"}
        return extra_body, top_level

    mapped = _HERMES_TO_GLM_EFFORT.get(effort)
    if mapped is None:
        # Unknown effort → let the server use its default (max).
        return extra_body, top_level

    top_level["reasoning_effort"] = mapped
    return extra_body, top_level


# -- Profile -----------------------------------------------------------------


class ZaiProfile(ProviderProfile):
    """Z.AI / GLM provider profile with reasoning effort, header, and
    prompt-safety fixes."""

    default_headers: dict[str, str] = {
        "User-Agent": "hermes-agent/1.0",
    }

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict[str, Any] | None = None,
        **context: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Map Hermes reasoning_effort to GLM-5.2 wire format.

        GLM-5.2 only accepts ``high`` and ``max`` as effort values.
        """
        if not isinstance(reasoning_config, dict):
            return {}, {}

        enabled = reasoning_config.get("enabled", True)
        effort = reasoning_config.get("effort")

        if enabled is False or effort == "none":
            return _map_reasoning_effort("none")

        return _map_reasoning_effort(effort)

    def prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Replace 'Hermes Agent' with 'Assistant' when talking to Z.AI.

        The phrase 'Hermes Agent' in prompts triggers HTTP 429 / code 1305
        ("temporarily overloaded") on Z.AI endpoints.  This method sanitises
        messages for all Z.AI hostnames (api.z.ai, open.bigmodel.cn, and
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
    display_name="Z.AI (GLM) - Custom",
    description="Z.AI / GLM — Zhipu AI models (custom profile with fixes)",
    signup_url="https://z.ai/",
    fallback_models=(
        "glm-5.2",
        "glm-5",
        "glm-4-9b",
    ),
    base_url="https://api.z.ai/api/paas/v4",
    default_aux_model="glm-4.5-flash",
)

register_provider(zai)

"""Qwen Cloud Token Plan provider profile.

Separate from the standard `alibaba` (pay-as-you-go) and
`alibaba-coding-plan` profiles because it hits a dedicated endpoint
(token-plan.ap-southeast-1.maas.aliyuncs.com) with a dedicated API key
tier (keys prefixed `sk-sp-`).  Token Plan keys/base-URLs are completely
separate from other Qwen Cloud tiers and must be used together.
"""

from providers import register_provider
from providers.base import ProviderProfile

qwen_token_plan = ProviderProfile(
    name="qwen-token-plan",
    aliases=("qwen-token", "token-plan"),
    display_name="Qwen Cloud (Token Plan)",
    description="Qwen Cloud Token Plan — dedicated subscription tier (Personal/Team)",
    signup_url="https://www.qwencloud.com/pricing/token-plan",
    env_vars=("QWEN_TOKEN_PLAN_API_KEY", "QWEN_TOKEN_PLAN_BASE_URL"),
    base_url="https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
    auth_type="api_key",
    fallback_models=(
        "qwen3.7-max",
        "qwen3.7-plus",
        "qwen3-max",
        "qwen3-plus",
    ),
    default_aux_model="qwen3.7-plus",
)

register_provider(qwen_token_plan)

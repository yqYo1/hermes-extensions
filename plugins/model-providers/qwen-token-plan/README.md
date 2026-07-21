# Qwen Cloud Token Plan Provider

A Hermes Agent model-provider plugin for [Qwen Cloud Token Plan](https://www.qwencloud.com/pricing/token-plan) — a dedicated subscription tier (Personal Edition) with its own endpoint and API keys.

## Why a separate provider?

Token Plan is **completely separate** from the pay-as-you-go DashScope (`DASHSCOPE_API_KEY`) and the Coding Plan (`ALIBABA_CODING_PLAN_API_KEY`):

- Dedicated endpoint: `token-plan.ap-southeast-1.maas.aliyuncs.com`
- Dedicated API keys prefixed `sk-sp-`
- Keys and base URLs must be used together and are not interchangeable across tiers

Using a dedicated provider avoids cross-tier credential confusion and keeps the `/model` picker clean.

## Supported models

The Personal Edition exposes the following reasoning models (see the [official overview](https://docs.qwencloud.com/token-plan/personal/token-plan-personal-overview)):

| Model | Family | Capabilities |
|-------|--------|-------------|
| `qwen3.8-max-preview` | Qwen | Reasoning, visual understanding, text generation |
| `qwen3.7-max` | Qwen | Reasoning, text generation |
| `qwen3.7-plus` | Qwen | Reasoning, visual understanding, text generation |
| `qwen3.6-flash` | Qwen | Reasoning, visual understanding, text generation |
| `glm-5.2` | Zhipu AI | Reasoning, text generation |
| `deepseek-v4-pro` | DeepSeek | Reasoning, text generation |

## Installation

```bash
mkdir -p ~/.hermes/plugins/model-providers/
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/plugins/model-providers/qwen-token-plan \
      ~/.hermes/plugins/model-providers/qwen-token-plan
```

Provider plugins auto-load on the next session. Verify with `hermes doctor`.

## Configuration

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `QWEN_TOKEN_PLAN_API_KEY` | Yes | Token Plan API key (starts with `sk-sp-`). Generated from the [Token Plan console](https://home.qwencloud.com/api-keys). Shown in full only once — save it immediately. |
| `QWEN_TOKEN_PLAN_BASE_URL` | No | Override the inference endpoint. Set this to switch protocols (see below). Falls back to the OpenAI-compatible default. |
| `QWEN_TOKEN_PLAN_THINKING_BUDGET_<LEVEL>` | No | Override the default `thinking_budget` (int, Qwen family) for a specific effort level. `<LEVEL>` is one of `MINIMAL`, `LOW`, `MEDIUM`, `HIGH`, `XHIGH`, `MAX`, `ULTRA`. Example: `QWEN_TOKEN_PLAN_THINKING_BUDGET_HIGH=49152`. |

Set the API key in `~/.hermes/.env`:

```bash
QWEN_TOKEN_PLAN_API_KEY=sk-sp-xxxxxxxx
```

### Base URL (protocol selection)

Token Plan supports two API protocols. Pick one via `model.base_url`:

| Protocol | Base URL | `api_mode` |
|----------|----------|------------|
| OpenAI compatible (default) | `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1` | `chat_completions` (auto-detected) |
| Anthropic compatible | `https://token-plan.ap-southeast-1.maas.aliyuncs.com/apps/anthropic` | `anthropic_messages` (auto-detected) |

`api_mode` is resolved by URL auto-detection — no need to set it explicitly.

### Example configurations

**OpenAI-compatible (default):**

```bash
hermes config set model.provider qwen-token-plan
hermes config set model.default qwen3.7-max
```

**Anthropic-compatible:**

```bash
hermes config set model.provider qwen-token-plan
hermes config set model.base_url https://token-plan.ap-southeast-1.maas.aliyuncs.com/apps/anthropic
hermes config set model.api_mode anthropic_messages
hermes config set model.default qwen3.7-max
```

## Thinking / reasoning control

Token Plan exposes three model families, each with a **different** thinking-control wire format on Qwen Cloud. This provider maps Hermes effort levels to the correct per-family parameters automatically.

### Effort hierarchy

Hermes effort levels (ascending): `minimal < low < medium < high < xhigh < max < ultra`. Set via `agent.reasoning_effort` in `config.yaml` or `/reasoning <level>` in chat.

### Per-family mapping

#### Qwen models (`qwen3.*`)

| Parameter | Type | Location | Description |
|-----------|------|----------|-------------|
| `enable_thinking` | bool | `extra_body` | Toggle thinking on/off. `false` when effort is `none`/disabled. |
| `thinking_budget` | int | `extra_body` | Max thinking tokens. Derived from effort level (overridable via env var). |
| `preserve_thinking` | bool | `extra_body` | Carry `reasoning_content` across turns. Enabled on supported models only. |

Models that support `preserve_thinking`: `qwen3.8-max-preview`, `qwen3.7-max`, `qwen3.7-plus`. Note: `qwen3.6-flash` does **not** support it.

#### GLM models (`glm-5.2`)

| Parameter | Type | Location | Description |
|-----------|------|----------|-------------|
| `enable_thinking` | bool | `extra_body` | Toggle thinking on/off. |
| `reasoning_effort` | str | top-level | One of `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`. Hermes `ultra` clamps to `max`. |

The GLM hierarchy matches Hermes 1:1 (same 7 levels). Reference: [Qwen Cloud GLM docs](https://docs.qwencloud.com/developer-guides/third-party-models/glm).

#### DeepSeek models (`deepseek-v4-pro`)

| Parameter | Type | Location | Description |
|-----------|------|----------|-------------|
| `enable_thinking` | bool | `extra_body` | Toggle thinking on/off. |
| `reasoning_effort` | str | top-level | One of `low`, `medium`, `high`, `xhigh`, `max`. Hermes levels collapse per the official mapping. |

Official mapping (per Qwen Cloud docs): `low`/`medium` behave as `high`; `xhigh` behaves as `max`. This provider maps: `minimal`/`low`/`medium`/`high` → `high`, `xhigh`/`max`/`ultra` → `max`. Reference: [Qwen Cloud DeepSeek docs](https://docs.qwencloud.com/developer-guides/third-party-models/deepseek).

> **Note:** `thinking_budget` is **not** sent for DeepSeek. The Qwen Cloud `thinking_budget` parameter applies only to "Qwen3 onward" models; DeepSeek-V4 is controlled via `reasoning_effort` alone.

### Disabled / none

For all families, effort `none` or `enabled: false` sends `enable_thinking: false` and nothing else.

### Thinking budget overrides

Default `thinking_budget` values per effort level (Qwen family):

| Effort | Default budget |
|--------|---------------|
| `minimal` | 512 |
| `low` | 2,048 |
| `medium` | 8,192 |
| `high` | 32,768 |
| `xhigh` | 65,536 |
| `max` | 131,072 |
| `ultra` | 262,144 |

These are conservative references. Override per level with the `QWEN_TOKEN_PLAN_THINKING_BUDGET_<LEVEL>` environment variable. When no effort is configured, no `thinking_budget` is sent (server default applies).

## Aliases

The provider resolves under any of: `qwen-token-plan`, `qwen-token`.

## References

- [Token Plan Personal overview](https://docs.qwencloud.com/token-plan/personal/token-plan-personal-overview)
- [Token Plan quickstart](https://docs.qwencloud.com/token-plan/personal/token-plan-personal-quickstart)
- [Thinking guide](https://docs.qwencloud.com/developer-guides/text-generation/thinking)
- [DeepSeek on Qwen Cloud](https://docs.qwencloud.com/developer-guides/third-party-models/deepseek)
- [GLM on Qwen Cloud](https://docs.qwencloud.com/developer-guides/third-party-models/glm)
- [Hermes Agent integration](https://docs.qwencloud.com/developer-guides/clients-and-developer-tools/hermes-agent)
- [Hermes Model Provider Plugin guide](https://hermes-agent.nousresearch.com/docs/developer-guide/model-provider-plugin)

# hermes-extensions

yqYo1's Hermes Agent plugins and skills collection.

## Overview

This repository collects self-made plugins and skills for Hermes Agent.

## Directory Structure

```
hermes-extensions/
├── plugins/                          # Hermes plugins
│   ├── browser-localhost-block/      # Blocks browser access to localhost
│   ├── delegate-task-full-inheritance/   # Blocks toolset limitation in delegate_task
│   └── model-providers/              # Model provider plugins (symlinked into ~/.hermes/plugins/model-providers/)
│       ├── qwen-token-plan/          # Qwen Cloud Token Plan (dedicated subscription tier)
│       └── zai/                       # Z.AI / GLM Coding Plan override (overrides builtin zai provider)
├── skills/                           # Hermes skills
│   └── git-workflow/                 # Git workflow documentation
├── LICENSE                           # MIT License
└── README.md                         # This file
```

## Plugins

### browser-localhost-block

Blocks browser tools from accessing localhost/127.0.0.1 and suggests using the tailscale IP instead.

**Purpose:**

- The browser backend runs on a separate instance from Hermes
- localhost would target the browser backend's own localhost, not the Hermes instance
- Enforces using tailscale IP (100.64.x.x) for cross-instance access

**Behavior:**

- Detects localhost/127.0.0.1 URLs in browser tool calls
- Dynamically retrieves the tailscale IP when blocking
- Returns error message with the tailscale IP as an alternative

### delegate-task-full-inheritance

Blocks `delegate_task` calls that specify a limited `toolsets` parameter.

**Purpose:**

- Forces subagents to inherit the parent's full toolset
- Prevents unintended capability restrictions

**Behavior:**

- Blocks when `toolsets` parameter is present in `delegate_task`
- Error message is sent to the LLM as well, prompting a retry

### qwen-token-plan (Model Provider)

Qwen Cloud Token Plan — dedicated subscription tier (Personal/Team Edition).

**Purpose:**

- Provides access to the Qwen Cloud Token Plan, a subscription-based tier separate from pay-as-you-go DashScope and the Coding Plan
- Uses dedicated API keys (prefixed `sk-sp-`) and a dedicated endpoint (`token-plan.ap-southeast-1.maas.aliyuncs.com`)
- Supports both OpenAI-compatible (default) and Anthropic-compatible protocols via `base_url` selection
- Maps Hermes reasoning effort to per-family thinking parameters (Qwen, GLM, DeepSeek)

**Installation:**

```bash
mkdir -p ~/.hermes/plugins/model-providers/
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/plugins/model-providers/qwen-token-plan ~/.hermes/plugins/model-providers/
hermes plugins enable qwen-token-plan-provider
```

For full documentation — supported models, environment variables, configuration examples, and per-family thinking/effort mapping — see the [plugin README](plugins/model-providers/qwen-token-plan/README.md).

**Configuration (OpenAI-compatible, default):**

```bash
hermes config set model.provider qwen-token-plan
hermes config set model.default qwen3.7-max
# Set API key in ~/.hermes/.env:
#   QWEN_TOKEN_PLAN_API_KEY=sk-sp-xxxxxxxx
```

**Configuration (Anthropic-compatible):**

```bash
hermes config set model.provider qwen-token-plan
hermes config set model.base_url https://token-plan.ap-southeast-1.maas.aliyuncs.com/apps/anthropic
hermes config set model.api_mode anthropic_messages
hermes config set model.default qwen3.7-max
```

### zai (Model Provider)

Z.AI / GLM model provider — overrides the builtin `zai` provider with Coding Plan tier.

**Purpose:**

- Overrides the builtin `zai` provider (last-writer-wins discovery) with:
  - **Coding Plan base URL** (`https://api.z.ai/api/coding/paas/v4`)
  - **OpenAI SDK User-Agent fingerprinting** (neutral `User-Agent` header)
  - **Prompt sanitization** — replaces "Hermes Agent" with "Assistant" to prevent 429/1305
- Inherits the builtin's reasoning logic: GLM-4.5+ thinking toggle + GLM-5.2 reasoning_effort mapping

**Installation:**

```bash
mkdir -p ~/.hermes/plugins/model-providers/
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/plugins/model-providers/zai ~/.hermes/plugins/model-providers/
hermes plugins enable zai
```

## Installation

### Clone the repository

```bash
ghq get git@github.com:yqYo1/hermes-extensions.git
```

### Install plugins

```bash
# Regular plugin (symlink directly to plugins/)
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/plugins/<plugin-name> ~/.hermes/plugins/

# Model-provider plugin (symlink into plugins/model-providers/)
mkdir -p ~/.hermes/plugins/model-providers/
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/plugins/model-providers/<name> ~/.hermes/plugins/model-providers/

# Enable
hermes plugins enable <plugin-name>
```

Symlinks allow instant updates via `git pull` in the repository.

### Install skills

```bash
# Symlink installation
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/skills/<skill-name> ~/.hermes/skills/
```

## License

MIT License - see [LICENSE](LICENSE) for details.

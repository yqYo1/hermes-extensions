# hermes-extensions

yqYo1's Hermes Agent plugins and skills collection.

## Overview

This repository collects self-made plugins and skills for Hermes Agent.

## Directory Structure

```
hermes-extensions/
├── plugins/                          # Hermes plugins
│   ├── browser-localhost-block/      # Blocks browser access to localhost
│   └── delegate-task-full-inheritance/   # Blocks toolset limitation in delegate_task
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

## Compatible Companions

### Hermes Tweet

[Hermes Tweet](https://github.com/Xquik-dev/hermes-tweet) is a native Hermes
Agent plugin for X/Twitter workflows. It fits alongside this collection when an
agent needs X/Twitter exploration, tweet/reply reads, user lookup, follower
export, monitoring, or explicitly gated actions.

Use it as a companion plugin rather than copying it into this repository:

```bash
git clone https://github.com/Xquik-dev/hermes-tweet.git ~/.hermes/plugins/hermes-tweet
hermes plugins enable hermes-tweet
```

Read workflows require `XQUIK_API_KEY`. Post, reply, and DM actions additionally
require `HERMES_TWEET_ENABLE_ACTIONS=true`, keeping reviewed actions opt-in.

## Installation

### Clone the repository

```bash
ghq get git@github.com:yqYo1/hermes-extensions.git
```

### Install plugins

```bash
# Symlink installation (recommended)
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/plugins/<plugin-name> ~/.hermes/plugins/

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

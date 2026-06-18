"""
browser-localhost-block
========================

A Hermes Agent plugin that blocks browser tools from accessing localhost
or 127.0.0.1, and suggests using the tailscale IP instead.

In this environment, the browser backend runs on a separate instance from
Hermes. Accessing localhost from the browser tool would connect to the
browser backend's localhost, not Hermes's localhost. This plugin enforces
using the tailscale IP (100.64.x.x) for cross-instance access.

The tailscale IP is retrieved dynamically when generating the block message,
rather than being hardcoded in the plugin.
"""

import json
import re
import subprocess
from typing import Any, Dict, Optional


# Browser tools that accept a URL parameter
_BROWSER_URL_TOOLS = frozenset(
    {
        "browser_navigate",
        "browser_click",
        "browser_type",
        "browser_press",
        "browser_scroll",
        "browser_snapshot",
        "browser_get_images",
        "browser_vision",
        "browser_console",
        "browser_back",
    }
)

# Patterns that indicate localhost / loopback access
_LOCALHOST_PATTERNS = [
    re.compile(r"^https?://localhost[\:/]", re.IGNORECASE),
    re.compile(r"^https?://127\.\d+\.\d+\.\d+[\:/]", re.IGNORECASE),
    re.compile(r"^https?://\[::1\][\:/]", re.IGNORECASE),
    re.compile(r"^http://localhost\b", re.IGNORECASE),
    re.compile(r"^http://127\.\d+\.\d+\.\d+\b", re.IGNORECASE),
]


def _get_tailscale_ip() -> Optional[str]:
    """Retrieve the tailscale IPv4 address dynamically.

    Tries multiple methods in order:
    1. ``tailscale ip -4`` (fastest, most reliable)
    2. ``ip addr`` / ``ifconfig`` grep for 100.64.x.x
    3. Parse ``tailscale status --json``

    Returns None if all methods fail.
    """
    # Method 1: tailscale CLI
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        ip = result.stdout.strip().splitlines()[0].strip()
        if ip:
            return ip
    except Exception:
        pass

    # Method 2: ip addr / ifconfig
    for cmd in (["ip", "addr"], ["ifconfig"]):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            # Tailscale IPs are in 100.64.0.0/10 (100.64.0.0 - 100.127.255.255)
            match = re.search(
                r"\b(100\.(?:6[4-9]|[7-9]\d|1[0-1]\d|12[0-7])\.\d+\.\d+)\b",
                result.stdout,
            )
            if match:
                return match.group(1)
        except Exception:
            pass

    # Method 3: tailscale status --json
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        data = json.loads(result.stdout)
        # Self node has TailscaleIPs
        ips = data.get("Self", {}).get("TailscaleIPs", [])
        for ip in ips:
            if ":" not in ip:  # Prefer IPv4
                return ip
        if ips:
            return ips[0]
    except Exception:
        pass

    return None


def _has_localhost_url(args: Optional[Dict[str, Any]]) -> Optional[str]:
    """Check if any URL argument points to localhost.

    Returns the matched URL string if found, None otherwise.
    """
    if not isinstance(args, dict):
        return None

    # Check common URL parameter names
    for key in ("url", "urls", "href", "link"):
        value = args.get(key)
        if not value:
            continue
        if isinstance(value, str):
            candidates = [value]
        elif isinstance(value, list):
            candidates = value
        else:
            continue

        for url in candidates:
            if not isinstance(url, str):
                continue
            for pattern in _LOCALHOST_PATTERNS:
                if pattern.search(url):
                    return url

    return None


def register(ctx):
    """Register the pre_tool_call hook that blocks localhost browser access."""

    def block_localhost_browser(
        tool_name: str,
        args: Optional[Dict[str, Any]],
        **kwargs,
    ) -> Optional[Dict[str, str]]:
        """Block browser tools from accessing localhost/127.0.0.1.

        When a browser tool is called with a localhost URL, this hook blocks
        the call and returns an error message suggesting the tailscale IP
        instead. The tailscale IP is retrieved dynamically at block time.
        """
        # Only intercept browser tools
        if tool_name not in _BROWSER_URL_TOOLS:
            return None

        # Check if the URL points to localhost
        matched_url = _has_localhost_url(args)
        if matched_url is None:
            return None

        # Dynamically retrieve tailscale IP
        tailscale_ip = _get_tailscale_ip()

        if tailscale_ip:
            message = (
                f"Browser tool blocked: attempted to access localhost "
                f"({matched_url}). Reason: The browser backend runs on a separate "
                f"instance from Hermes, so localhost/127.0.0.1 would target the "
                f"browser backend's own localhost, not the Hermes instance. "
                f"Use the tailscale IP instead: http://{tailscale_ip}/"
            )
        else:
            message = (
                f"Browser tool blocked: attempted to access localhost "
                f"({matched_url}). Reason: The browser backend runs on a separate "
                f"instance from Hermes, so localhost/127.0.0.1 would target the "
                f"browser backend's own localhost, not the Hermes instance. "
                f"Please bind your service to the tailscale interface and use "
                f"the tailscale IP (100.64.x.x) for access. "
                f"Run 'tailscale ip' to find your IP."
            )

        return {"action": "block", "message": message}

    ctx.register_hook("pre_tool_call", block_localhost_browser)

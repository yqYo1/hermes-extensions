"""
delegate-task-full-inheritance
==============================

A Hermes Agent plugin that prevents limiting toolsets in delegate_task calls.

When a subagent is spawned with an explicit ``toolsets`` parameter, this plugin
blocks the call and returns an error explaining that full toolset inheritance is
required. This ensures subagents have the same capabilities as the parent agent.

The block message is returned as a tool error, so the LLM sees it and can retry
without the toolsets restriction.
"""

from typing import Any, Dict, Optional


def register(ctx):
    """
    Register the pre_tool_call hook that blocks delegate_task with limited toolsets.
    """

    def block_limited_delegate_task(
        tool_name: str,
        args: Optional[Dict[str, Any]],
        **kwargs,
    ) -> Optional[Dict[str, str]]:
        """
        Block delegate_task calls that specify a limited toolsets parameter.

        This hook enforces the policy that subagents must inherit the parent's
        full toolset. Any attempt to restrict available tools via the
        ``toolsets`` parameter is blocked with a descriptive error message.

        The error message is returned as a tool error, which is visible to both
        the user and the LLM. The LLM can then retry without the toolsets
        restriction.
        """
        # Only intercept delegate_task calls
        if tool_name != "delegate_task":
            return None

        if not isinstance(args, dict):
            return None

        # --- Single-task mode: check top-level toolsets ---
        toolsets = args.get("toolsets")
        if toolsets is not None:
            return {
                "action": "block",
                "message": (
                    "delegate_task with explicit 'toolsets' parameter is blocked. "
                    "Subagents must inherit the parent's full toolset. "
                    "Remove the 'toolsets' parameter to allow full inheritance."
                ),
            }

        # --- Batch mode: check each task in the tasks array ---
        tasks = args.get("tasks")
        if isinstance(tasks, list):
            for i, task in enumerate(tasks):
                if isinstance(task, dict) and task.get("toolsets") is not None:
                    return {
                        "action": "block",
                        "message": (
                            f"delegate_task batch mode: task {i} has explicit "
                            f"'toolsets' parameter. Subagents must inherit the "
                            f"parent's full toolset. Remove 'toolsets' from "
                            f"task {i} to allow full inheritance."
                        ),
                    }

        # No toolsets restriction found — allow the call
        return None

    ctx.register_hook("pre_tool_call", block_limited_delegate_task)

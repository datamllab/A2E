"""τ²-bench tool schemas — built from the real tool names in the full task set.

Each tool name comes from the vendored tasks' ``expected_actions`` (the real
sierra tau2-bench tool calls), so the agent can call exactly the tools the tasks
expect and ``tool_recall`` is meaningful. Arguments are an open object; the
executor acknowledges calls (state-free stub).
"""

from __future__ import annotations

from typing import Any

from ageneval.task.datasets.tau2._vendor import VENDOR_TOOL_NAMES


def get_tau2_tool_schemas() -> list[dict[str, Any]]:
    """Return OpenAI-format schemas for every tool used by the vendored tasks."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": f"τ²-bench tool '{name}' (tool-agent-user task action).",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": True},
            },
        }
        for name in VENDOR_TOOL_NAMES
    ]

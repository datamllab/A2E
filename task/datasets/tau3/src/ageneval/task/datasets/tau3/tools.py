"""τ³-bench tool schemas.

Built from the real tool names appearing in the vendored tasks'
``evaluation_criteria.actions`` (the official dev/tau3 expected actions), so the
agent can call exactly the tools the tasks expect and ``tool_recall`` is
meaningful. Arguments are an open object (the upstream tool signatures are
domain-specific); the executor acknowledges calls, mirroring the τ2 adapter.
"""

from __future__ import annotations

from typing import Any

from ageneval.task.datasets.tau3._vendor import VENDOR_TOOL_NAMES


def get_tau3_tool_schemas() -> list[dict[str, Any]]:
    """Return OpenAI-format schemas for every tool used by the vendored tasks."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": f"τ³-bench tool '{name}' (tool-agent-user task action).",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True,
                },
            },
        }
        for name in VENDOR_TOOL_NAMES
    ]

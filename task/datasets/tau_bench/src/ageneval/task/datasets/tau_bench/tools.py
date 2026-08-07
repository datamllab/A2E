"""OpenAI-style tool schemas for τ-bench (v1).

Built from the real tool names in the vendored full task set
(``evaluation_criteria`` actions), so the agent can call exactly the tools the
tasks expect and ``tool_recall`` is meaningful. The ``domain`` parameter is kept
for interface compatibility; the schema is the union of all τ-bench tool names
(extra tools are harmless — the agent picks the ones it needs).
"""

from __future__ import annotations

from typing import Any, Literal

from ageneval.task.datasets.tau_bench._vendor import VENDOR_TOOL_NAMES

Domain = Literal["retail", "airline"]


def get_tool_schemas(domain: Domain | None = None) -> list[dict[str, Any]]:
    """Return tool schemas (real τ-bench tool names; ``domain`` kept for compat)."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": f"τ-bench tool '{name}' (tool-agent-user task action).",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": True},
            },
        }
        for name in VENDOR_TOOL_NAMES
    ]

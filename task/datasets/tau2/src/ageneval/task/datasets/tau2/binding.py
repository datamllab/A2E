"""τ2-bench binding — tool-calling agent (parallel to τ-bench)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from ageneval.task.core import AgentBinding
from ageneval.task.datasets.tau2.tools import get_tau2_tool_schemas


def build_tau2_binding() -> AgentBinding:
    tools = get_tau2_tool_schemas()
    return AgentBinding(
        name="tau2",
        tool_schemas=tools,
        tool_executor=_tau2_tool_executor,
        system_prompt_builder=lambda toolset: _build_system_prompt(toolset),
    )


def _build_system_prompt(tools: Sequence[Mapping[str, Any]]) -> str:
    tool_block = "\n".join(
        f"- {t['function']['name']}: {t['function'].get('description', '')}\n"
        f"  parameters: {json.dumps(t['function'].get('parameters', {}))}"
        for t in tools
    )
    return (
        "You are a τ2-bench retail support agent. Use the listed tools to fulfil the request.\n"
        "Reply each turn with a single JSON object: either\n"
        '  {"action": "<tool_name>", "arguments": {...}}\n'
        "or, when finished,\n"
        '  {"final_answer": "<text>"}\n'
        f"AVAILABLE TOOLS:\n{tool_block}\n"
    )


def _tau2_tool_executor(name: str, args: Mapping[str, Any], state: Mapping[str, Any]) -> Any:
    if name == "find_user":
        return state.get("user", {"error": "no user"})
    if name == "find_order":
        oid = args.get("order_id")
        for o in state.get("orders", []):
            if o.get("id") == oid:
                return o
        return {"error": "order not found"}
    # All other tools are stubbed (acknowledge).
    return {"ok": True, "tool": name, "echo": dict(args)}

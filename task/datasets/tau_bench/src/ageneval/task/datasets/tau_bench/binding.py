"""τ-bench → generic-agent ``AgentBinding`` bundle.

Lets any framework-agnostic agent (LangGraph, claude-sdk, …) handle τ-bench
without having to import τ-bench-specific code itself. Adding a new
benchmark works the same way: a sibling ``task/datasets/<bench>/binding.py``
exposes its own ``build_<bench>_binding()``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from ageneval.task.core import AgentBinding
from ageneval.task.datasets.tau_bench.tools import get_tool_schemas

Domain = Literal["retail", "airline"]


def build_tau_bench_binding(domain: Domain = "retail") -> AgentBinding:
    """Return everything a generic agent needs to run τ-bench in ``domain``."""
    tool_schemas = get_tool_schemas(domain)
    return AgentBinding(
        name=f"tau-bench-{domain}",
        tool_schemas=tool_schemas,
        tool_executor=_make_tau_tool_executor(domain),
        system_prompt_builder=lambda tools: _build_tau_system_prompt(domain, tools),
    )


# ─── tool executor ────────────────────────────────────────────────────────────


def _make_tau_tool_executor(domain: Domain):
    """Closure-over-domain dispatcher that maps tool name → handler."""

    def execute(name: str, arguments: Mapping[str, Any], state: Mapping[str, Any]) -> Any:
        handler = _RETAIL_TOOLS.get(name) if domain == "retail" else _AIRLINE_TOOLS.get(name)
        if handler is None:
            return {"ok": True, "tool": name, "echo": dict(arguments)}
        return handler(arguments, state)

    return execute


def _find_user(args: Mapping[str, Any], state: Mapping[str, Any]) -> Any:
    return state.get("user", {"error": "no user"})


def _find_order(args: Mapping[str, Any], state: Mapping[str, Any]) -> Any:
    order_id = args.get("order_id")
    for o in state.get("orders", []):
        if o.get("id") == order_id:
            return o
    return {"error": "order not found"}


def _ack(args: Mapping[str, Any], _state: Mapping[str, Any]) -> Any:
    """Generic stub: acknowledge the call so the agent can move on."""
    return {"ok": True, "echo": dict(args)}


_RETAIL_TOOLS = {
    "find_user": _find_user,
    "find_order": _find_order,
    "cancel_order": _ack,
    "create_return": _ack,
    "update_shipping_address": _ack,
}

_AIRLINE_TOOLS = {
    "find_user": _find_user,
    "book_flight": _ack,
    "modify_reservation": _ack,
    "cancel_reservation": _ack,
}


# ─── system prompt ────────────────────────────────────────────────────────────


def _build_tau_system_prompt(domain: Domain, tools: Sequence[Mapping[str, Any]]) -> str:
    tool_block = "\n".join(
        f"- {t['function']['name']}: {t['function'].get('description', '')}\n"
        f"  parameters: {json.dumps(t['function'].get('parameters', {}))}"
        for t in tools
    )
    return (
        f"You are a helpful customer-service agent for a {domain} company.\n"
        "Use the tools listed below to satisfy the user's request. Reply each\n"
        "turn with one JSON object: either\n"
        '  {"action": "<tool_name>", "arguments": {...}}\n'
        "or, when finished,\n"
        '  {"final_answer": "<text>"}\n\n'
        f"AVAILABLE TOOLS:\n{tool_block}\n"
    )

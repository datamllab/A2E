"""τ³-bench binding — tool-calling agent over the TEXT (no-voice) tasks.

Parallel to the τ2 binding: a JSON-action protocol plus an executor that serves
lightweight state lookups and acknowledges every other tool. The benchmark's
voice modality is not used — this is a pure text tool-agent-user interaction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ageneval.task.core import AgentBinding
from ageneval.task.datasets.tau3.tools import get_tau3_tool_schemas

# Tool-name families that can be answered from the task's initial_state.
_USER_TOOLS = {"find_user", "find_user_id_by_name_zip", "find_user_id_by_email", "get_user_details"}
_ORDER_TOOLS = {"get_order_details", "find_order", "get_reservation_details"}


def build_tau3_binding() -> AgentBinding:
    """Return everything a generic agent needs to drive a τ³-bench text task."""
    return AgentBinding(
        name="tau3",
        tool_schemas=get_tau3_tool_schemas(),
        tool_executor=_tau3_tool_executor,
        system_prompt_builder=_build_system_prompt,
    )


def _build_system_prompt(tools: Sequence[Mapping[str, Any]]) -> str:
    tool_block = "\n".join(
        f"- {t['function']['name']}: {t['function'].get('description', '')}" for t in tools
    )
    return (
        "You are a τ³-bench customer-support agent handling a TEXT conversation "
        "(the benchmark's voice modality is not used here). Use the listed tools "
        "to fulfil the user's request while following standard domain policy.\n"
        "Reply each turn with a single JSON object: either\n"
        '  {"action": "<tool_name>", "arguments": {...}}\n'
        "or, when finished,\n"
        '  {"final_answer": "<text>"}\n'
        f"AVAILABLE TOOLS:\n{tool_block}\n"
    )


def _tau3_tool_executor(name: str, args: Mapping[str, Any], state: Mapping[str, Any]) -> Any:
    if name in _USER_TOOLS:
        return state.get("user", {"ok": True, "tool": name, "echo": dict(args)})
    if name in _ORDER_TOOLS:
        return state.get("order") or {"ok": True, "tool": name, "echo": dict(args)}
    # All other domain tools are acknowledged (state-free stub), as in τ2.
    return {"ok": True, "tool": name, "echo": dict(args)}

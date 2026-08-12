"""τ-bench → generic-agent ``AgentBinding`` bundle.

Uses the official Sierra wiki as the system prompt and the live tool executor
backed by a per-task database deepcopy. Native function-calling harnesses
(Agno, smolagents, …) receive real parameter schemas; LangGraph still asks
the router for a JSON action in its own user prompt.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from ageneval.task.core import AgentBinding
from ageneval.task.datasets.tau_bench.runtime import (
    build_system_prompt,
    execute_tool,
    get_tool_schemas,
)

Domain = Literal["retail", "airline"]


def build_tau_bench_binding(domain: Domain = "retail") -> AgentBinding:
    resolved: Domain = "airline" if domain == "airline" else "retail"
    tool_schemas = get_tool_schemas(resolved)
    wiki = build_system_prompt(resolved)
    return AgentBinding(
        name=f"tau-bench-{resolved}",
        tool_schemas=tool_schemas,
        tool_executor=_make_executor(resolved),
        system_prompt_builder=lambda _tools, _wiki=wiki: _wiki,
    )


def _make_executor(domain: Domain):
    def execute(name: str, arguments: Mapping[str, Any], state: Mapping[str, Any]) -> Any:
        return execute_tool(name, arguments, state, domain=domain)

    return execute

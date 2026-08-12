"""τ²-bench binding — domain-specific live tools (retail / airline).

Telecom/mock tasks keep the old name-only schemas only when an unknown domain
is requested; the default and CLI path use retail or airline so harnesses get
real parameter schemas and a mutable database.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ageneval.task.core import AgentBinding
from ageneval.task.datasets.tau_bench.runtime import (
    Domain,
    build_system_prompt,
    execute_tool,
    get_tool_schemas,
)


def _resolve_domain(domain: str | None) -> Domain:
    if domain == "airline":
        return "airline"
    if domain in (None, "", "retail", "all"):
        return "retail"
    raise ValueError(
        f"unsupported tau2 domain {domain!r}; live tools exist for retail/airline only"
    )


def build_tau2_binding(domain: str | None = "retail") -> AgentBinding:
    resolved = _resolve_domain(domain)
    wiki = build_system_prompt(resolved)
    return AgentBinding(
        name=f"tau2-{resolved}",
        tool_schemas=get_tool_schemas(resolved),
        tool_executor=_make_executor(resolved),
        system_prompt_builder=lambda _tools, _wiki=wiki: _wiki,
    )


def _make_executor(domain: Domain):
    def execute(name: str, arguments: Mapping[str, Any], state: Mapping[str, Any]) -> Any:
        return execute_tool(name, arguments, state, domain=domain)

    return execute

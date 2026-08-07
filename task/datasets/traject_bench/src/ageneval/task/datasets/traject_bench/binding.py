"""traject-bench binding — tool-calling agent over the assistant-utilities domain."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from ageneval.task.core import AgentBinding
from ageneval.task.datasets.traject_bench.tools import (
    get_traject_bench_tool_schemas,
    traject_bench_tool_executor,
)


def build_traject_bench_binding() -> AgentBinding:
    """Build the AgentBinding for the traject-bench tool-calling dataset."""
    tools = get_traject_bench_tool_schemas()
    return AgentBinding(
        name="traject-bench",
        tool_schemas=tools,
        tool_executor=traject_bench_tool_executor,
        system_prompt_builder=_build_system_prompt,
    )


def _build_system_prompt(tools: Sequence[Mapping[str, Any]]) -> str:
    tool_block = "\n".join(
        f"- {t['function']['name']}: {t['function'].get('description', '')}\n"
        f"  parameters: {json.dumps(t['function'].get('parameters', {}))}"
        for t in tools
    )
    return (
        "You are a traject-bench assistant. Use the listed tools to fulfil the "
        "user's request — most tasks need one or two tool calls.\n"
        "Reply each turn with a single JSON object: either\n"
        '  {"action": "<tool_name>", "arguments": {...}}\n'
        "to call a tool, or, once you have the answer,\n"
        '  {"final_answer": "<text>"}\n'
        f"AVAILABLE TOOLS:\n{tool_block}\n"
    )

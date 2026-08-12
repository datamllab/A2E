"""DeepSearchQA binding — web_search / open_url over the live web."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from ageneval.task.core import AgentBinding
from ageneval.task.datasets.deepsearchqa.tools import (
    deepsearchqa_tool_executor,
    get_deepsearchqa_tool_schemas,
)


def build_deepsearchqa_binding() -> AgentBinding:
    tools = get_deepsearchqa_tool_schemas()
    return AgentBinding(
        name="deepsearchqa",
        tool_schemas=tools,
        tool_executor=deepsearchqa_tool_executor,
        system_prompt_builder=_build_system_prompt,
    )


def _build_system_prompt(tools: Sequence[Mapping[str, Any]]) -> str:
    tool_block = "\n".join(
        f"- {t['function']['name']}: {t['function'].get('description', '')}\n"
        f"  parameters: {json.dumps(t['function'].get('parameters', {}))}"
        for t in tools
    )
    return (
        "You are a DeepSearchQA research agent. The user asks a multi-step "
        "factual question that must be answered from the open web.\n"
        "You MUST call web_search at least once before answering. "
        "You MUST open official source URLs with open_url "
        "(NHS, federalreserve.gov, or whichever site the question names). "
        "Do not answer from memory. Do not substitute Wikipedia for those sites.\n"
        "Use the listed tools via the function-calling interface with their "
        "named arguments (query=... / url=...). Do not emit a JSON action "
        "object as plain text. "
        "When you have the answer, reply with one JSON object only:\n"
        '  {"final_answer": "<concise answer>"}\n'
        "For list questions, put every required item in final_answer, "
        "separated by commas. Do not mention hidden labels such as "
        "answer_type.\n"
        f"AVAILABLE TOOLS:\n{tool_block}\n"
    )

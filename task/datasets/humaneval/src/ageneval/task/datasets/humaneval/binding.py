"""HumanEval binding — no tools, return Python code as ``final_answer``."""

from __future__ import annotations

from ageneval.task.core import AgentBinding


def build_humaneval_binding() -> AgentBinding:
    return AgentBinding(
        name="humaneval",
        tool_schemas=(),
        tool_executor=lambda *_, **__: {},
        system_prompt_builder=lambda _: (
            "You are a senior Python engineer. Complete the function so it passes the "
            "hidden tests. Return a SINGLE JSON object with the function body (no "
            "imports, no markdown fence):\n"
            '  {"final_answer": "    # your code here"}'
        ),
    )

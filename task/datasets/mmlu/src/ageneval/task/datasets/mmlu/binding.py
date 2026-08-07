"""MMLU binding — no tools, just answer the multi-choice question."""

from __future__ import annotations

from ageneval.task.core import AgentBinding


def build_mmlu_binding() -> AgentBinding:
    """Return a tool-less binding suitable for MMLU multi-choice QA."""
    return AgentBinding(
        name="mmlu",
        tool_schemas=(),
        tool_executor=lambda *_, **__: {},  # never called
        system_prompt_builder=lambda _: (
            "You are answering a multiple-choice exam. Read the question and pick the "
            "best option. Reply with a single JSON object:\n"
            '  {"final_answer": "<A|B|C|D>"}\n'
            "Do not add anything outside the JSON."
        ),
    )

"""GSM8K binding — no tools; answer should be a single number."""

from __future__ import annotations

from ageneval.task.core import AgentBinding


def build_gsm8k_binding() -> AgentBinding:
    return AgentBinding(
        name="gsm8k",
        tool_schemas=(),
        tool_executor=lambda *_, **__: {},
        system_prompt_builder=lambda _: (
            "Solve the math problem. Show brief reasoning, then output a single "
            "JSON object: {\"final_answer\": \"<number>\"}. The final_answer must "
            "contain only digits (and optional minus / decimal point)."
        ),
    )

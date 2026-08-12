"""PersistBench binding — no tools; recall stated facts in JSON."""

from __future__ import annotations

from ageneval.task.core import AgentBinding


def build_persistbench_binding() -> AgentBinding:
    return AgentBinding(
        name="persistbench",
        tool_schemas=(),
        tool_executor=lambda *_, **__: {},
        system_prompt_builder=lambda _: (
            "You are evaluated on knowledge persistence: recall the fact the user "
            "previously stated and answer concisely. Reply with a single JSON object:\n"
            '  {"final_answer": "<short answer>"}'
        ),
    )

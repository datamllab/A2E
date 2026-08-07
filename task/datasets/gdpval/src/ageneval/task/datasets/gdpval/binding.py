"""GDPval binding — tool-less; the agent's reply *is* the deliverable.

Unlike the QA-suite bindings (which demand a ``{"final_answer": "<letter>"}``
envelope), a GDPval deliverable is a long professional document. We therefore do
NOT force a JSON wrapper: the agent answers in plain text and the runner captures
the whole response as ``TaskTrace.final_answer`` (agno uses ``result.content``).
An LLM judge then grades that text against the task rubric.
"""

from __future__ import annotations

from ageneval.task.core import AgentBinding

_SYSTEM_PROMPT = (
    "You are a top-tier professional completing a real-world, economically "
    "valuable work task in your field of expertise. Read the user's request "
    "carefully and produce the COMPLETE requested deliverable directly as your "
    "reply.\n"
    "- Match the format the task asks for (report, memo, table, spreadsheet "
    "contents, plan, analysis, code, etc.).\n"
    "- If the task references attached files you cannot see, state your "
    "assumptions explicitly and still deliver a full, usable result.\n"
    "- Be thorough, accurate and well-structured. Your reply is the final "
    "deliverable — do not ask clarifying questions."
)


def build_gdpval_binding() -> AgentBinding:
    """Return a tool-less ``AgentBinding`` for GDPval deliverable generation."""
    return AgentBinding(
        name="gdpval",
        tool_schemas=(),
        tool_executor=lambda *_, **__: {},  # never called (no tools)
        system_prompt_builder=lambda _: _SYSTEM_PROMPT,
    )

"""QA Suite binding — tool-less bindings, one per benchmark answer type."""

from __future__ import annotations

from ageneval.task.core import AgentBinding

from ageneval.task.datasets.qa_suite.benchmarks import BENCHMARKS

_PROMPTS = {
    "mc": (
        "You are answering a multiple-choice exam question. Read the question and "
        "the lettered options, then pick the single best option. Reply with one "
        'JSON object only:\n  {"final_answer": "<letter>"}\n'
        "where <letter> is one of A, B, C, … Do not add anything outside the JSON."
    ),
    "numeric": (
        "Solve the problem. Show brief reasoning, then output one JSON object only:\n"
        '  {"final_answer": "<number>"}\n'
        "The final_answer must be the final numeric answer (digits, optional minus "
        "sign / decimal point / fraction). Do not add anything outside the JSON."
    ),
    "freeform": (
        "Answer the question concisely. Reply with one JSON object only:\n"
        '  {"final_answer": "<short answer>"}\n'
        "Keep the answer as short as possible. Do not add anything outside the JSON."
    ),
}


def build_qa_binding(benchmark: str) -> AgentBinding:
    """Return a tool-less ``AgentBinding`` for a QA Suite benchmark.

    Args:
        benchmark: Key into ``BENCHMARKS``.

    Returns:
        An ``AgentBinding`` with no tools and an answer-type-specific system prompt.

    Raises:
        KeyError: Unknown ``benchmark`` key.
    """
    cfg = BENCHMARKS[benchmark]
    prompt = _PROMPTS[cfg.answer_type]
    return AgentBinding(
        name=f"qa-{benchmark}",
        tool_schemas=(),
        tool_executor=lambda *_, **__: {},  # never called
        system_prompt_builder=lambda _: prompt,
    )

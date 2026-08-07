"""Correctness and conciseness evaluator logic."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from a2e.evals.llm import LLM

from core.eval_common import (
    _as_dict,
    _build_text_prompt,
    _dual_mode,
    _final_answer,
    _first_expected,
    _instruction,
    _json_dumps,
    _task_output,
    _text_judge,
    _tool_history_block,
)


def make_correctness(llm: LLM) -> Callable[..., dict[str, Any]]:
    from a2e.evals.metrics import CorrectnessEvaluator

    return _dual_mode(
        metric_name="correctness",
        build_structured=lambda llm_: CorrectnessEvaluator(llm=llm_),
        structured_input=lambda output, expected, input_: {
            "input": (
                _instruction(input_)
                + "\n\nTask execution evidence:\n"
                + _json_dumps(
                    {
                        "resolved": _task_output(output).get("resolved"),
                        "status": _task_output(output).get("status"),
                        "error": _task_output(output).get("error"),
                        "swe_status": _task_output(output).get("swe_status"),
                    }
                )
                + "\n\n"
                + _tool_history_block(output)
            ),
            "output": _final_answer(output),
        },
        text_definition="Is the agent's output factually correct and complete given the question?",
        choices=("correct", "incorrect"),
        positive="correct",
        text_context=lambda output, expected, input_: {
            "Question": _instruction(input_),
            "Agent answer": _final_answer(output),
            "Expected answer hint": _first_expected(expected),
            "Task execution evidence": _json_dumps(
                {
                    "resolved": _task_output(output).get("resolved"),
                    "status": _task_output(output).get("status"),
                    "error": _task_output(output).get("error"),
                    "swe_status": _task_output(output).get("swe_status"),
                }
            ),
            "Tool history": _tool_history_block(output) or "(no tool calls)",
        },
        llm=llm,
    )


def make_conciseness(llm: LLM) -> Callable[..., dict[str, Any]]:
    from a2e.evals.metrics import ConcisenessEvaluator

    return _dual_mode(
        metric_name="conciseness",
        build_structured=lambda llm_: ConcisenessEvaluator(llm=llm_),
        structured_input=lambda output, expected, input_: {
            "input": _instruction(input_),
            "output": _final_answer(output),
        },
        text_definition="Is the agent's output concise, with only necessary information?",
        choices=("concise", "verbose"),
        positive="concise",
        text_context=lambda output, expected, input_: {
            "Question": _instruction(input_),
            "Agent answer": _final_answer(output),
        },
        llm=llm,
    )


def make_llm_judge(llm: LLM, label: str = "llm_judge") -> Callable[..., dict[str, Any]]:
    def llm_judge(output: dict[str, Any], expected: dict[str, Any], input: dict[str, Any]) -> dict[str, Any]:
        prompt = _build_text_prompt(
            metric_name=label,
            definition=(
                "Judge whether the agent's final answer satisfies the instruction. Use the expected "
                "answer hint when present, and otherwise rely on the task instruction and trajectory evidence."
            ),
            choices=("correct", "incorrect"),
            positive="correct",
            context={
                "Task instruction": _instruction(input),
                "Final answer": _final_answer(output),
                "Expected answer hint": _first_expected(expected),
                "Tool history": _tool_history_block(output) or "(no tool calls)",
            },
        )
        return _text_judge(llm, prompt, ("correct", "incorrect"), "correct")

    llm_judge.__name__ = label
    llm_judge.__qualname__ = label
    return llm_judge


def make_instruction_following(llm: LLM) -> Callable[..., dict[str, Any]]:
    def instruction_following(
        output: dict[str, Any], expected: dict[str, Any], input: dict[str, Any]
    ) -> dict[str, Any]:
        prompt = _build_text_prompt(
            metric_name="instruction_following",
            definition=(
                "Judge whether the agent followed every explicit user instruction and subrequest. "
                "Penalize missing required work, wrong topic, ignored constraints, or partial completion."
            ),
            choices=("followed", "partial", "wrong_topic"),
            positive="followed",
            context={
                "Task instruction": _instruction(input),
                "Final answer": _final_answer(output),
                "Task execution evidence": _json_dumps(
                    {
                        "resolved": _task_output(output).get("resolved"),
                        "status": _task_output(output).get("status"),
                        "error": _task_output(output).get("error"),
                    }
                ),
                "Tool history": _tool_history_block(output) or "(no tool calls)",
            },
        )
        return _text_judge(llm, prompt, ("followed", "partial", "wrong_topic"), "followed")

    instruction_following.__name__ = "instruction_following"
    instruction_following.__qualname__ = "instruction_following"
    return instruction_following

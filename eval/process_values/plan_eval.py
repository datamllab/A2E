"""APB-aligned plan metric evaluator logic."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from a2e.evals.llm import LLM

from core.eval_common import (
    _as_dict,
    _available_tools_str,
    _build_text_prompt,
    _final_answer,
    _first_expected,
    _initial_state_str,
    _instruction,
    _json_dumps,
    _text_judge,
    _tool_history_block,
)


def _plan_context(output: dict[str, Any], expected: dict[str, Any], input: dict[str, Any]) -> dict[str, str]:
    expected_dict = _as_dict(expected)
    return {
        "Task instruction": _instruction(input),
        "Initial state": _initial_state_str(input),
        "Expected/reference answer": _first_expected(expected),
        "Expected/reference metadata": _json_dumps(expected_dict, limit=2500) if expected_dict else "",
        "Available tools": _available_tools_str(input),
        "Final answer": _final_answer(output),
        "Observed tool/action trajectory": _tool_history_block(output) or "(no tool calls)",
    }


def _apb_judge(
    llm: LLM,
    *,
    metric_name: str,
    definition: str,
    choices: Sequence[str],
    positive: str,
) -> Callable[..., dict[str, Any]]:
    def evaluator(output: dict[str, Any], expected: dict[str, Any], input: dict[str, Any]) -> dict[str, Any]:
        prompt = _build_text_prompt(
            metric_name=metric_name,
            definition=definition,
            choices=choices,
            positive=positive,
            context=_plan_context(output, expected, input),
        )
        return _text_judge(llm, prompt, choices, positive)

    evaluator.__name__ = metric_name
    evaluator.__qualname__ = metric_name
    return evaluator


def make_plan_grade(llm: LLM) -> Callable[..., dict[str, Any]]:
    choices = (
        "perfect",
        "very_good",
        "mostly_correct",
        "partially_correct",
        "mostly_incorrect",
        "failed",
    )
    label_scores = {
        "perfect": 1.0,
        "very_good": 0.8,
        "mostly_correct": 0.6,
        "partially_correct": 0.4,
        "mostly_incorrect": 0.2,
        "failed": 0.0,
    }

    def plan_grade(output: dict[str, Any], expected: dict[str, Any], input: dict[str, Any]) -> dict[str, Any]:
        prompt = _build_text_prompt(
            metric_name="plan_grade",
            definition=(
                "Grade plan quality following Agent Planning Benchmark (APB) Plan Grade. "
                "Evaluate functional viability and logical soundness, not surface similarity to a reference. "
                "Detect all relevant APB errors independently: E1 goal misunderstanding, E2 task "
                "incompleteness or premature conclusion, E3 constraint violation, E4 logical defect, "
                "E5 tool-use error, and E6 hallucination. Use perfect/1.0 when all errors are absent "
                "and the plan is logically sound and solves the query. Use very_good/0.8 for an almost "
                "perfect plan with only a minor non-critical issue. Use mostly_correct/0.6 when the "
                "main logical flow is captured but one key component is missing or flawed. Use "
                "partially_correct/0.4 when some correct steps exist but the overall sequence is wrong "
                "or fundamentally broken. Use mostly_incorrect/0.2 when the plan is deeply flawed but "
                "has limited logical merit. Use failed/0.0 for zero logical merit, complete hallucination, "
                "or complete goal misunderstanding."
            ),
            choices=choices,
            positive="perfect",
            context=_plan_context(output, expected, input),
        )
        result = _text_judge(llm, prompt, choices, "perfect")
        label = str(result.get("label") or "")
        if label in label_scores:
            result["score"] = label_scores[label]
        return result

    plan_grade.__name__ = "plan_grade"
    plan_grade.__qualname__ = "plan_grade"
    return plan_grade


def make_plan_goal_alignment(llm: LLM) -> Callable[..., dict[str, Any]]:
    return _apb_judge(
        llm,
        metric_name="plan_goal_alignment",
        definition=(
            "Judge the inverse of APB E1_GOAL_UNDERSTANDING. Label aligned with score 1.0 "
            "only when the plan preserves the user's core intent. Label misaligned with score 0.0 "
            "when the plan fundamentally misunderstands, deviates from, or contradicts the user's "
            "query objective. Different valid solution paths must not be penalized."
        ),
        choices=("aligned", "misaligned"),
        positive="aligned",
    )


def make_plan_completeness(llm: LLM) -> Callable[..., dict[str, Any]]:
    return _apb_judge(
        llm,
        metric_name="plan_completeness",
        definition=(
            "Judge the inverse of APB E2_TASK_COMPLETENESS / E2_PREMATURE_CONCLUSION. "
            "Label complete with score 1.0 when the plan covers all required subtasks and does "
            "not conclude before necessary intermediate evidence or actions are obtained. Label "
            "incomplete with score 0.0 when required subtasks are missing or the plan answers/stops "
            "prematurely."
        ),
        choices=("complete", "incomplete"),
        positive="complete",
    )


def make_plan_constraint_adherence(llm: LLM) -> Callable[..., dict[str, Any]]:
    return _apb_judge(
        llm,
        metric_name="plan_constraint_adherence",
        definition=(
            "Judge the inverse of APB E3_CONSTRAINT_VIOLATION. Label adhered with score 1.0 "
            "when the plan respects all explicit constraints from the user query, system/task prompt, "
            "required output format, allowed tools, time range, data source, method, scope, and safety "
            "boundary. Label violated with score 0.0 when any explicit constraint is violated."
        ),
        choices=("adhered", "violated"),
        positive="adhered",
    )


def make_reasoning_coherence(llm: LLM) -> Callable[..., dict[str, Any]]:
    return _apb_judge(
        llm,
        metric_name="reasoning_coherence",
        definition=(
            "Judge the inverse of APB E4_LOGICAL_DEFECT. Label coherent with score 1.0 when the "
            "plan's reasoning flow is logically sound: each step has the required premises, uses "
            "available evidence correctly, does not require data or results that have not been obtained, "
            "does not ignore already-obtained data, and avoids circular or risky reasoning. Label "
            "logic_error with score 0.0 when causal errors, ordering errors, missing prerequisites, "
            "unsupported dependencies, or circular logic appear."
        ),
        choices=("coherent", "logic_error"),
        positive="coherent",
    )


def make_plan_hallucination(llm: LLM) -> Callable[..., dict[str, Any]]:
    return _apb_judge(
        llm,
        metric_name="plan_hallucination",
        definition=(
            "Judge the inverse of APB E6_HALLUCINATION_ERROR. Label grounded with score 1.0 when "
            "the plan does not call non-existent tools, reference non-existent data, invent unavailable "
            "intermediate results, or state factual claims contrary to the provided context. Label "
            "hallucinated with score 0.0 when the plan uses a non-existent tool, fabricates data/results, "
            "or relies on evidence that is not available at that step."
        ),
        choices=("grounded", "hallucinated"),
        positive="grounded",
    )

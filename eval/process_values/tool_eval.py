"""Tool metric evaluator logic."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from a2e.evals.llm import LLM

from core.eval_common import (
    _as_dict,
    _available_tools_str,
    _build_text_prompt,
    _dual_mode,
    _enrich_output,
    _final_answer,
    _initial_state_str,
    _instruction,
    _json_dumps,
    _text_judge,
    _tool_history_block,
)


def make_tool_recall(
    spans_by_example_id: Mapping[str, Sequence[Mapping[str, Any]]],
    llm: LLM | None = None,
) -> Callable[..., dict[str, Any]]:
    def tool_recall(
        output: dict[str, Any],
        expected: dict[str, Any],
        input: dict[str, Any],
        example: Any = None,
    ) -> dict[str, Any]:
        example_id = str(getattr(example, "id", "") or _as_dict(example).get("id") or "")
        enriched = _enrich_output(output, spans_by_example_id.get(example_id, []))
        called = set(enriched.get("tool_calls") or [])
        expected_names = {
            action.get("name")
            for action in (_as_dict(expected).get("expected_actions") or [])
            if isinstance(action, Mapping) and action.get("name")
        }
        if not expected_names:
            if llm is not None:
                prompt = _build_text_prompt(
                    metric_name="tool_recall",
                    definition=(
                        "For this terminal-bench task, judge whether the agent's tool usage "
                        "covered the necessary operations to solve the task. Consider whether "
                        "it inspected relevant files, edited or created required artifacts, ran "
                        "appropriate verification commands, handled tool errors, and avoided "
                        "stopping before the task was complete."
                    ),
                    choices=("complete", "incomplete"),
                    positive="complete",
                    context={
                        "Question": _instruction(input),
                        "Task execution evidence": _json_dumps(
                            {
                                "resolved": enriched.get("resolved"),
                                "status": enriched.get("status"),
                                "error": enriched.get("error"),
                                "swe_status": enriched.get("swe_status"),
                                "turns": enriched.get("turns"),
                            }
                        ),
                        "Tools called": _json_dumps(enriched.get("tool_calls") or []),
                        "Tool history": _tool_history_block(enriched) or "(no tool calls)",
                        "Final answer": _final_answer(enriched),
                    },
                )
                result = _text_judge(llm, prompt, ("complete", "incomplete"), "complete")
                result["explanation"] = (
                    "expected_actions is empty; used LLM trajectory judge fallback. "
                    + str(result.get("explanation") or "")
                )[:1000]
                return result
            return {
                "score": 1.0,
                "label": "no_expected_tools",
                "explanation": "expected_actions is empty; tool recall is vacuously 1.0",
            }
        hits = called & expected_names
        score = len(hits) / len(expected_names)
        return {
            "score": float(score),
            "label": "complete" if score >= 1.0 else "missed",
            "explanation": (
                f"called={sorted(called)}; expected={sorted(expected_names)}; "
                f"hit={sorted(hits)}; recall={score:.3f}"
            ),
        }

    tool_recall.__name__ = "tool_recall"
    tool_recall.__qualname__ = "tool_recall"
    return tool_recall


def _tool_selection_str(output: dict[str, Any]) -> str:
    output_dict = _as_dict(output)
    full = output_dict.get("tool_calls_full") or []
    if full:
        return _json_dumps(
            [
                {
                    "name": _as_dict(call).get("name"),
                    "arguments": _as_dict(call).get("arguments") or {},
                }
                for call in full
            ],
            limit=6000,
        )
    return _json_dumps(output_dict.get("tool_calls") or [], limit=2000)


def _task_execution_evidence(output: dict[str, Any]) -> str:
    return _json_dumps(
        {
            "resolved": output.get("resolved"),
            "status": output.get("status"),
            "error": output.get("error"),
            "swe_status": output.get("swe_status"),
            "turns": output.get("turns"),
        },
        limit=4000,
    )


def make_tool_selection(llm: LLM) -> Callable[..., dict[str, Any]]:
    from a2e.evals.metrics import ToolSelectionEvaluator

    return _dual_mode(
        metric_name="tool_selection",
        build_structured=lambda llm_: ToolSelectionEvaluator(llm=llm_),
        structured_input=lambda output, expected, input_: {
            "input": _instruction(input_),
            "available_tools": _available_tools_str(input_),
            "tool_selection": _tool_selection_str(output),
        },
        text_definition=(
            "Were the selected tools appropriate for the task, given the available tool menu "
            "and the visible trajectory?"
        ),
        choices=("correct", "incorrect"),
        positive="correct",
        text_context=lambda output, expected, input_: {
            "Question": _instruction(input_),
            "Available tools": _available_tools_str(input_),
            "Tool selection": _tool_selection_str(output),
            "Task execution evidence": _task_execution_evidence(output),
        },
        llm=llm,
    )


def make_tool_invocation(llm: LLM) -> Callable[..., dict[str, Any]]:
    from a2e.evals.metrics import ToolInvocationEvaluator

    return _dual_mode(
        metric_name="tool_invocation",
        build_structured=lambda llm_: ToolInvocationEvaluator(llm=llm_),
        structured_input=lambda output, expected, input_: {
            "input": _instruction(input_) + "\n\nVisible state:\n" + _initial_state_str(input_),
            "available_tools": _available_tools_str(input_),
            "tool_selection": _tool_selection_str(output),
        },
        text_definition=(
            "Were the tool invocations correctly formatted, grounded in visible state, "
            "schema-compatible, and free of unsafe or hallucinated arguments?"
        ),
        choices=("correct", "incorrect"),
        positive="correct",
        text_context=lambda output, expected, input_: {
            "Question": _instruction(input_),
            "Visible state": _initial_state_str(input_),
            "Available tools": _available_tools_str(input_),
            "Tool invocations": _tool_selection_str(output),
            "Tool history": _tool_history_block(output),
        },
        llm=llm,
    )


def make_tool_call_count(
    spans_by_example_id: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Callable[..., dict[str, Any]]:
    def tool_call_count(
        output: dict[str, Any],
        expected: dict[str, Any],
        input: dict[str, Any],
        example: Any = None,
    ) -> dict[str, Any]:
        example_id = str(getattr(example, "id", "") or _as_dict(example).get("id") or "")
        enriched = _enrich_output(output, spans_by_example_id.get(example_id, []))
        count = len(enriched.get("tool_calls") or enriched.get("tool_calls_full") or [])
        if count == 0:
            label = "none"
        elif count < 3:
            label = "low"
        elif count < 6:
            label = "medium"
        else:
            label = "high"
        return {"score": float(count), "label": label, "explanation": f"{count} tool call(s)"}

    tool_call_count.__name__ = "tool_call_count"
    tool_call_count.__qualname__ = "tool_call_count"
    return tool_call_count


def _tool_schema_name(item: Any) -> str | None:
    item_dict = _as_dict(item)
    tool = item_dict.get("tool") if isinstance(item_dict.get("tool"), Mapping) else item_dict
    tool_dict = _as_dict(tool)
    raw_schema = tool_dict.get("json_schema")
    schema: dict[str, Any] = {}
    if isinstance(raw_schema, str):
        try:
            schema = json.loads(raw_schema)
        except json.JSONDecodeError:
            schema = {}
    elif isinstance(raw_schema, Mapping):
        schema = dict(raw_schema)
    function = _as_dict(schema.get("function"))
    return str(schema.get("name") or function.get("name") or tool_dict.get("name") or item_dict.get("name") or "") or None


def _available_tool_names_from_spans(spans: Sequence[Mapping[str, Any]]) -> set[str]:
    names: set[str] = set()
    for span in spans:
        attrs = _as_dict(span.get("attributes"))
        llm = _as_dict(attrs.get("llm"))
        for item in llm.get("tools") or []:
            name = _tool_schema_name(item)
            if name:
                names.add(name)
    return names


def _actual_tool_names_from_spans(spans: Sequence[Mapping[str, Any]]) -> list[str]:
    names: list[str] = []
    for span in spans:
        attrs = _as_dict(span.get("attributes"))
        kind = str(span.get("span_kind") or _as_dict(_as_dict(attrs.get("openinference")).get("span")).get("kind") or "")
        if kind.upper() != "TOOL":
            continue
        tool = _as_dict(attrs.get("tool"))
        name = str(tool.get("name") or attrs.get("tool.name") or span.get("name") or "")
        if name:
            names.append(name)
    return names


def make_tool_hallucination(
    spans_by_example_id: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Callable[..., dict[str, Any]]:
    def tool_hallucination(
        output: dict[str, Any],
        expected: dict[str, Any],
        input: dict[str, Any],
        example: Any = None,
    ) -> dict[str, Any]:
        example_id = str(getattr(example, "id", "") or _as_dict(example).get("id") or "")
        spans = spans_by_example_id.get(example_id, [])
        available = _available_tool_names_from_spans(spans)
        called = _actual_tool_names_from_spans(spans)
        if not called:
            return {
                "score": 1.0,
                "label": "no_tool_calls",
                "explanation": "No actual TOOL spans were observed.",
            }
        if not available:
            return {
                "score": 0.0,
                "label": "unmeasured",
                "explanation": "Actual TOOL spans exist, but no available tool schemas were found in LLM spans.",
            }
        hallucinated = sorted({name for name in called if name not in available})
        valid_count = sum(1 for name in called if name in available)
        score = valid_count / len(called)
        return {
            "score": float(score),
            "label": "clean" if not hallucinated else "hallucinated",
            "explanation": (
                f"called={sorted(set(called))}; available_count={len(available)}; "
                f"hallucinated={hallucinated}; score={score:.3f}"
            ),
        }

    tool_hallucination.__name__ = "tool_hallucination"
    tool_hallucination.__qualname__ = "tool_hallucination"
    return tool_hallucination


def _is_error_result(value: Any) -> bool:
    text = _json_dumps(value, limit=1200).lower()
    markers = ("error", "exception", "traceback", "failed", "failure", "not found", "invalid", "timeout")
    return any(marker in text for marker in markers)


def make_self_correction_rate(
    spans_by_example_id: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Callable[..., dict[str, Any]]:
    def self_correction_rate(
        output: dict[str, Any],
        expected: dict[str, Any],
        input: dict[str, Any],
        example: Any = None,
    ) -> dict[str, Any]:
        example_id = str(getattr(example, "id", "") or _as_dict(example).get("id") or "")
        enriched = _enrich_output(output, spans_by_example_id.get(example_id, []))
        calls = [_as_dict(call) for call in (enriched.get("tool_calls_full") or [])]
        error_indices = [idx for idx, call in enumerate(calls) if _is_error_result(call.get("result"))]
        if not error_indices:
            return {
                "score": 1.0,
                "label": "no_errors",
                "explanation": "No tool error outputs were observed.",
            }

        corrected = 0
        for idx in error_indices:
            name = calls[idx].get("name")
            if any(call.get("name") == name and not _is_error_result(call.get("result")) for call in calls[idx + 1 :]):
                corrected += 1
        score = corrected / len(error_indices)
        return {
            "score": float(score),
            "label": "corrected" if score >= 1.0 else "uncorrected",
            "explanation": (
                f"{corrected} corrected error(s) / {len(error_indices)} observed tool error(s); "
                f"score={score:.3f}"
            ),
        }

    self_correction_rate.__name__ = "self_correction_rate"
    self_correction_rate.__qualname__ = "self_correction_rate"
    return self_correction_rate

"""Shared evaluator helpers.

This module contains only trace/output normalization and LLM judge helpers. Server
I/O stays in `deal_server.py`; metric-specific scoring stays in the metric modules.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from a2e.evals.llm import LLM

LOGGER = logging.getLogger("a2e_eval_common")

_LABEL_RE = re.compile(r"LABEL\s*=\s*([\w-]+)", re.IGNORECASE)
_SCORE_RE = re.compile(r"SCORE\s*=\s*([01](?:\.\d+)?)", re.IGNORECASE)
_EXPL_RE = re.compile(r"EXPLANATION\s*=\s*(.+?)(?:\n|$)", re.IGNORECASE | re.DOTALL)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _task_output(value: Any) -> dict[str, Any]:
    value_dict = _as_dict(value)
    nested = value_dict.get("task_output")
    if isinstance(nested, Mapping):
        return dict(nested)
    return value_dict


def _json_dumps(value: Any, limit: int | None = None) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value)
    return text if limit is None else text[:limit]


def _final_answer(output: Any) -> str:
    return str(_task_output(output).get("final_answer") or "")


def _instruction(input_: Any) -> str:
    return str(_as_dict(input_).get("instruction") or "")


def _first_expected(expected: Any) -> str:
    outs = _as_dict(expected).get("expected_outputs") or []
    return str(outs[0]) if outs else ""


def _initial_state_str(input_: Any) -> str:
    state = _as_dict(input_).get("initial_state")
    return _json_dumps(state, limit=4000) if state else ""


def _available_tools_str(input_: Any) -> str:
    tools = _as_dict(input_).get("available_tools") or []
    if not tools:
        return "<not recorded>"
    if isinstance(tools, list):
        lines: list[str] = []
        for tool in tools:
            if isinstance(tool, Mapping):
                name = tool.get("name", "?")
                desc = str(tool.get("description") or "").strip()
                lines.append(f"- {name}: {desc}" if desc else f"- {name}")
            else:
                lines.append(f"- {tool}")
        return "\n".join(lines)
    return _json_dumps(tools)


def _span_attributes(span: Mapping[str, Any]) -> dict[str, Any]:
    return _as_dict(span.get("attributes"))


def _span_sort_key(span: Mapping[str, Any]) -> str:
    return str(span.get("start_time") or "")


def _tool_calls_from_spans(spans: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for span in sorted(spans, key=_span_sort_key):
        attrs = _span_attributes(span)
        kind = str(span.get("span_kind") or attrs.get("openinference.span.kind") or "").upper()
        if kind != "TOOL":
            continue
        tool_attr = attrs.get("tool") if isinstance(attrs.get("tool"), Mapping) else {}
        input_attr = attrs.get("input") if isinstance(attrs.get("input"), Mapping) else {}
        output_attr = attrs.get("output") if isinstance(attrs.get("output"), Mapping) else {}
        name = (
            tool_attr.get("name")
            or attrs.get("tool.name")
            or attrs.get("function.name")
            or span.get("name")
            or "unknown_tool"
        )
        arguments = (
            tool_attr.get("parameters")
            or attrs.get("tool.parameters")
            or attrs.get("tool.arguments")
            or input_attr.get("value")
            or attrs.get("llm.input_messages.0.message.tool_calls.0.tool_call.function.arguments")
            or {}
        )
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except Exception:
                arguments = {"raw": arguments}
        result = (
            output_attr.get("value")
            or attrs.get("tool.output")
            or attrs.get("tool.output.value")
            or attrs.get("output.value")
            or attrs.get("output")
        )
        calls.append({"name": str(name), "arguments": arguments or {}, "result": result})
    return calls


def _tool_history_block(output: Any) -> str:
    output_dict = _as_dict(output)
    full = output_dict.get("tool_calls_full") or []
    if not full:
        return ""
    lines = ["Tool history (what the agent verified via tools, in order):"]
    for call in full:
        call_dict = _as_dict(call)
        name = call_dict.get("name", "?")
        args = _json_dumps(call_dict.get("arguments") or {}, limit=400)
        result = _json_dumps(call_dict.get("result"), limit=600)
        lines.append(f"  - {name}({args}) -> {result}")
    return "\n".join(lines)


def _enrich_output(output: Any, spans: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    output_dict = dict(_task_output(output))
    if not output_dict.get("tool_calls_full"):
        tool_calls_full = _tool_calls_from_spans(spans)
        if tool_calls_full:
            output_dict["tool_calls_full"] = tool_calls_full
    if not output_dict.get("tool_calls") and output_dict.get("tool_calls_full"):
        output_dict["tool_calls"] = [
            str(call.get("name"))
            for call in output_dict["tool_calls_full"]
            if isinstance(call, Mapping) and call.get("name")
        ]
    return output_dict


def _numeric_attr(attrs: Mapping[str, Any], key: str) -> float | None:
    value = attrs.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _token_cost_spans(spans: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    llm_spans = [
        span
        for span in spans
        if str(span.get("span_kind") or "").upper() == "LLM"
        and any(key.startswith("llm.token_count.") or key.startswith("llm.cost.") for key in _span_attributes(span))
    ]
    if llm_spans:
        return llm_spans
    return [
        span
        for span in spans
        if any(key.startswith("llm.token_count.") or key.startswith("llm.cost.") for key in _span_attributes(span))
    ]


def _sum_total_tokens(spans: Sequence[Mapping[str, Any]]) -> tuple[float, str]:
    total = 0.0
    used = 0
    for span in _token_cost_spans(spans):
        attrs = _span_attributes(span)
        span_total = _numeric_attr(attrs, "llm.token_count.total")
        if span_total is None:
            prompt = _numeric_attr(attrs, "llm.token_count.prompt") or 0.0
            completion = _numeric_attr(attrs, "llm.token_count.completion") or 0.0
            span_total = prompt + completion if prompt or completion else None
        if span_total is not None:
            total += span_total
            used += 1
    return total, f"summed from {used} span(s)"


def _sum_cost(spans: Sequence[Mapping[str, Any]]) -> tuple[float, str]:
    total = 0.0
    used = 0
    for span in _token_cost_spans(spans):
        attrs = _span_attributes(span)
        span_cost = _numeric_attr(attrs, "llm.cost.total")
        if span_cost is None:
            prompt = _numeric_attr(attrs, "llm.cost.prompt") or 0.0
            completion = _numeric_attr(attrs, "llm.cost.completion") or 0.0
            span_cost = prompt + completion if prompt or completion else None
        if span_cost is not None:
            total += span_cost
            used += 1
    return total, f"summed from {used} span(s)"


def _score_to_dict(scores: Any) -> dict[str, Any]:
    score = scores[0] if isinstance(scores, list) and scores else scores
    if score is None:
        return {"score": 0.0, "label": "error", "explanation": "no score returned"}
    raw_score = getattr(score, "score", None)
    raw_label = getattr(score, "label", None)
    raw_explanation = getattr(score, "explanation", None)
    return {
        "score": float(raw_score) if raw_score is not None else 0.0,
        "label": str(raw_label) if raw_label is not None else "",
        "explanation": str(raw_explanation or "")[:1000],
    }


def _build_text_prompt(
    *,
    metric_name: str,
    definition: str,
    choices: Sequence[str],
    positive: str,
    context: Mapping[str, str],
) -> str:
    rendered = "\n".join(f"{key}: {value}" for key, value in context.items() if value)
    choices_csv = " | ".join(choices)
    return (
        "You are evaluating an AI agent's output.\n\n"
        f"Metric: {metric_name}\n"
        f"Definition: {definition}\n"
        f"Valid labels: {choices_csv}\n\n"
        "Return EXACTLY one line, no other prose:\n"
        f"LABEL=<one of: {choices_csv}>; SCORE=<{positive}=1 else 0>; "
        "EXPLANATION=<one sentence why>\n\n"
        f"{rendered or '(no extra context)'}\n"
    )


def _text_judge(llm: LLM, prompt: str, choices: Sequence[str], positive: str) -> dict[str, Any]:
    try:
        text = llm.generate_text(prompt=prompt) or ""
    except Exception as exc:
        return {
            "score": 0.0,
            "label": "error",
            "explanation": f"text-mode call failed: {type(exc).__name__}: {exc}"[:500],
        }

    label_match = _LABEL_RE.search(text)
    raw_label = label_match.group(1).lower() if label_match else ""
    label = next((choice for choice in choices if choice.lower() == raw_label), "")
    if not label:
        label = next(
            (choice for choice in choices if choice.lower() in raw_label or raw_label in choice.lower()),
            "",
        )
    score_match = _SCORE_RE.search(text)
    score = float(score_match.group(1)) if score_match else (1.0 if label == positive else 0.0)
    explanation_match = _EXPL_RE.search(text)
    explanation = explanation_match.group(1).strip() if explanation_match else text[:200]
    return {"score": score, "label": label or "error", "explanation": explanation[:1000]}


def _dual_mode(
    *,
    metric_name: str,
    build_structured: Callable[[LLM], Any],
    structured_input: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]],
    text_definition: str,
    choices: Sequence[str],
    positive: str,
    text_context: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], Mapping[str, str]],
    llm: LLM,
) -> Callable[..., dict[str, Any]]:
    structured = build_structured(llm)
    state = {"structured_ok": None}

    def runner(output: dict[str, Any], expected: dict[str, Any], input: dict[str, Any]) -> dict[str, Any]:
        if state["structured_ok"] is not False:
            try:
                result = _score_to_dict(structured.evaluate(structured_input(output, expected, input)))
                state["structured_ok"] = True
                return result
            except Exception as exc:
                LOGGER.debug(
                    "structured evaluator %s failed; switching to text mode: %s: %s",
                    metric_name,
                    type(exc).__name__,
                    exc,
                )
                state["structured_ok"] = False

        prompt = _build_text_prompt(
            metric_name=metric_name,
            definition=text_definition,
            choices=choices,
            positive=positive,
            context=text_context(output, expected, input),
        )
        return _text_judge(llm, prompt, choices, positive)

    runner.__name__ = metric_name
    runner.__qualname__ = metric_name
    return runner


def _make_enriching_llm_evaluator(
    metric_name: str,
    base_evaluator: Callable[..., dict[str, Any]],
    spans_by_example_id: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Callable[..., dict[str, Any]]:
    def evaluator(
        output: dict[str, Any],
        expected: dict[str, Any],
        input: dict[str, Any],
        example: Any = None,
    ) -> dict[str, Any]:
        example_id = str(getattr(example, "id", "") or _as_dict(example).get("id") or "")
        enriched = _enrich_output(output, spans_by_example_id.get(example_id, []))
        return base_evaluator(enriched, expected, input)

    evaluator.__name__ = metric_name
    evaluator.__qualname__ = metric_name
    return evaluator

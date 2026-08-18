#!/usr/bin/env python3
"""Self-contained Colab demo — no git clone, no API keys, no eval package install."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

CODE_METRICS = (
    "task_succeeded",
    "tool_recall",
    "tool_call_count",
    "tool_hallucination",
    "self_correction_rate",
    "total_token_usage",
    "turn_count",
)


def _unscored(reason: str) -> dict[str, Any]:
    return {"score": None, "label": "unscored", "explanation": str(reason)[:1000]}


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
        tool_attr = _as_dict(attrs.get("tool"))
        output_attr = _as_dict(attrs.get("output"))
        name = tool_attr.get("name") or attrs.get("tool.name") or span.get("name") or "unknown_tool"
        result = output_attr.get("value") or attrs.get("tool.output") or attrs.get("output")
        calls.append({"name": str(name), "arguments": {}, "result": result})
    return calls


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


def _score_task_succeeded(output: dict[str, Any], expected: dict[str, Any], input_: dict[str, Any]) -> dict[str, Any]:
    status = str(_task_output(output).get("status") or "").lower()
    if not status:
        return _unscored("task_output.status is missing; task_succeeded cannot be scored")
    score = 1.0 if status == "ok" else 0.0
    return {
        "score": score,
        "label": "ok" if score else status,
        "explanation": f"status={status}",
    }


def _score_tool_recall(
    output: dict[str, Any],
    expected: dict[str, Any],
    input_: dict[str, Any],
    *,
    spans: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    enriched = _enrich_output(output, spans)
    called = set(enriched.get("tool_calls") or [])
    expected_names = {
        action.get("name")
        for action in (_as_dict(expected).get("expected_actions") or [])
        if isinstance(action, Mapping) and action.get("name")
    }
    hits = called & expected_names
    if not expected_names:
        return _unscored("expected_actions is empty; tool_recall cannot be scored without required tool names")
    score = len(hits) / len(expected_names)
    return {
        "score": float(score),
        "label": "complete" if score >= 1.0 else "missed",
        "explanation": f"called={sorted(called)}; expected={sorted(expected_names)}; hit={sorted(hits)}",
    }


def _score_tool_call_count(
    output: dict[str, Any],
    expected: dict[str, Any],
    input_: dict[str, Any],
    *,
    spans: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    enriched = _enrich_output(output, spans)
    count = len(enriched.get("tool_calls") or enriched.get("tool_calls_full") or [])
    label = "none" if count == 0 else "low" if count < 3 else "medium" if count < 6 else "high"
    return {"score": float(count), "label": label, "explanation": f"{count} tool call(s)"}


def _actual_tool_names_from_spans(spans: Sequence[Mapping[str, Any]]) -> list[str]:
    names: list[str] = []
    for span in spans:
        attrs = _span_attributes(span)
        kind = str(span.get("span_kind") or "").upper()
        if kind != "TOOL":
            continue
        tool = _as_dict(attrs.get("tool"))
        name = str(tool.get("name") or attrs.get("tool.name") or span.get("name") or "")
        if name:
            names.append(name)
    return names


def _score_tool_hallucination(
    output: dict[str, Any],
    expected: dict[str, Any],
    input_: dict[str, Any],
    *,
    spans: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    called = _actual_tool_names_from_spans(spans)
    if not called:
        return _unscored("No TOOL spans observed; tool_hallucination is not applicable.")
    available = {str(t.get("name")) for t in (_as_dict(input_).get("available_tools") or []) if t.get("name")}
    if not available:
        return _unscored("No available_tools in input; tool_hallucination cannot be scored.")
    hallucinated = sorted({name for name in called if name not in available})
    valid_count = sum(1 for name in called if name in available)
    score = valid_count / len(called)
    return {
        "score": float(score),
        "label": "clean" if not hallucinated else "hallucinated",
        "explanation": f"called={sorted(set(called))}; hallucinated={hallucinated}",
    }


def _is_error_result(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, default=str).lower()
    markers = ("error", "exception", "traceback", "failed", "failure", "not found", "invalid", "timeout")
    return any(marker in text for marker in markers)


def _score_self_correction_rate(
    output: dict[str, Any],
    expected: dict[str, Any],
    input_: dict[str, Any],
    *,
    spans: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    enriched = _enrich_output(output, spans)
    calls = [_as_dict(call) for call in (enriched.get("tool_calls_full") or [])]
    error_indices = [idx for idx, call in enumerate(calls) if _is_error_result(call.get("result"))]
    if not error_indices:
        return _unscored("No tool error outputs observed; self_correction_rate is not applicable.")
    corrected = sum(
        1
        for idx in error_indices
        if any(
            call.get("name") == calls[idx].get("name") and not _is_error_result(call.get("result"))
            for call in calls[idx + 1 :]
        )
    )
    score = corrected / len(error_indices)
    return {
        "score": float(score),
        "label": "corrected" if score >= 1.0 else "uncorrected",
        "explanation": f"{corrected}/{len(error_indices)} tool errors corrected",
    }


def _score_total_token_usage(
    output: dict[str, Any],
    expected: dict[str, Any],
    input_: dict[str, Any],
    *,
    spans: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    total, source = _sum_total_tokens(spans)
    if total == 0:
        return _unscored(f"token usage is missing; {source}")
    label = "low" if total < 2000 else "medium" if total < 10000 else "high"
    return {"score": float(total), "label": label, "explanation": f"{total:.0f} tokens; {source}"}


def _score_turn_count(output: dict[str, Any], expected: dict[str, Any], input_: dict[str, Any]) -> dict[str, Any]:
    output_dict = _task_output(output)
    raw = output_dict.get("turns")
    if raw is None:
        raw = output_dict.get("turn_count")
    if raw is None:
        return _unscored("turn_count is missing from task output")
    try:
        count = int(raw)
    except (TypeError, ValueError):
        return _unscored(f"turn_count is not numeric: {raw!r}")
    label = "zero" if count == 0 else "low" if count < 3 else "medium" if count < 8 else "high"
    return {"score": float(count), "label": label, "explanation": f"{count} turn(s)"}


def score_run(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    spans = run.get("spans") or []
    output = run.get("output") or {}
    expected = run.get("expected") or {}
    input_ = run.get("input") or {}
    return {
        "task_succeeded": _score_task_succeeded(output, expected, input_),
        "tool_recall": _score_tool_recall(output, expected, input_, spans=spans),
        "tool_call_count": _score_tool_call_count(output, expected, input_, spans=spans),
        "tool_hallucination": _score_tool_hallucination(output, expected, input_, spans=spans),
        "self_correction_rate": _score_self_correction_rate(output, expected, input_, spans=spans),
        "total_token_usage": _score_total_token_usage(output, expected, input_, spans=spans),
        "turn_count": _score_turn_count(output, expected, input_),
    }


def default_demo_payload() -> dict[str, Any]:
    data_path = Path(__file__).resolve().parent / "data" / "colab_demo_pair.json"
    if data_path.exists():
        return json.loads(data_path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"Demo data not found: {data_path}")


def run_demo(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or default_demo_payload()
    rows: list[dict[str, Any]] = []
    print("=" * 72)
    print("A²E Colab demo — offline CODE metrics (standalone, no clone)")
    print(payload.get("description", ""))
    print("=" * 72)

    for run in payload.get("runs") or []:
        label = run.get("label") or run.get("harness") or "run"
        scores = score_run(run)
        print(f"\n### {label} ({run.get('harness')})")
        for metric in CODE_METRICS:
            item = scores[metric]
            print(
                f"  {metric:22s}  score={item.get('score')}  "
                f"label={item.get('label')}  "
                f"{str(item.get('explanation') or '')[:80]}"
            )
            rows.append(
                {
                    "harness": run.get("harness"),
                    "label": label,
                    "metric": metric,
                    "score": item.get("score"),
                    "result_label": item.get("label"),
                    "explanation": item.get("explanation"),
                }
            )

    return {"rows": rows, "metrics": list(CODE_METRICS)}


def main() -> int:
    result = run_demo()
    print("\n__DEMO_JSON__")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

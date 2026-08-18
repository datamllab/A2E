#!/usr/bin/env python3
"""Colab-friendly offline metric demo: score two sample trajectories (no AE2 server)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

NOTEBOOK_DIR = Path(__file__).resolve().parent
REPO_ROOT = NOTEBOOK_DIR.parent
EVAL_ROOT = REPO_ROOT / "eval"

for path in (EVAL_ROOT,):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from core.agent_eval import make_task_succeeded  # noqa: E402
from process_values.tool_eval import (  # noqa: E402
    make_self_correction_rate,
    make_tool_call_count,
    make_tool_hallucination,
    make_tool_recall,
)
from result_values.efficiency_eval import make_total_token_usage, make_turn_count  # noqa: E402

CODE_METRICS = (
    "task_succeeded",
    "tool_recall",
    "tool_call_count",
    "tool_hallucination",
    "self_correction_rate",
    "total_token_usage",
    "turn_count",
)


def _build_evaluators(example_id: str, spans: list[dict[str, Any]]) -> dict[str, Any]:
    spans_by_example_id = {example_id: spans}
    return {
        "task_succeeded": make_task_succeeded(),
        "tool_recall": make_tool_recall(spans_by_example_id, llm=None),
        "tool_call_count": make_tool_call_count(spans_by_example_id),
        "tool_hallucination": make_tool_hallucination(spans_by_example_id),
        "self_correction_rate": make_self_correction_rate(spans_by_example_id),
        "total_token_usage": make_total_token_usage(spans_by_example_id),
        "turn_count": make_turn_count(),
    }


def _call_evaluator(fn, *, output, expected, input_, example) -> dict[str, Any]:
    import inspect

    kwargs = {"output": output, "expected": expected, "input": input_}
    if "example" in inspect.signature(fn).parameters:
        kwargs["example"] = example
    return fn(**kwargs)


def _score_run(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    example_id = str(run["example_id"])
    evaluators = _build_evaluators(example_id, run.get("spans") or [])
    example = {"id": example_id}
    results: dict[str, dict[str, Any]] = {}
    for name, fn in evaluators.items():
        results[name] = _call_evaluator(
            fn,
            output=run.get("output") or {},
            expected=run.get("expected") or {},
            input_=run.get("input") or {},
            example=example,
        )
    return results


def main() -> int:
    data_path = NOTEBOOK_DIR / "data" / "colab_demo_pair.json"
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []

    print("=" * 72)
    print("A²E Colab demo — offline CODE metrics on two sample trajectories")
    print(payload.get("description", ""))
    print("=" * 72)

    for run in payload.get("runs") or []:
        label = run.get("label") or run.get("harness") or "run"
        scores = _score_run(run)
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

    # Emit JSON line for notebook pandas ingestion
    print("\n__DEMO_JSON__")
    print(json.dumps({"rows": rows, "metrics": list(CODE_METRICS)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

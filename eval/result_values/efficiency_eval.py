"""Efficiency metric evaluator logic."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from core.eval_common import _as_dict, _final_answer, _sum_cost, _sum_total_tokens, _task_output


def _count_answer_tokens(text: str) -> tuple[int, str]:
    if not text:
        return 0, "empty final_answer"
    try:
        import tiktoken

        return len(tiktoken.get_encoding("cl100k_base").encode(text)), "tiktoken cl100k_base"
    except Exception:
        return max(1, len(text) // 4), "len(text)//4 fallback"


def make_total_token_usage(
    spans_by_example_id: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Callable[..., dict[str, Any]]:
    def total_token_usage(
        output: dict[str, Any],
        expected: dict[str, Any],
        input: dict[str, Any],
        example: Any = None,
    ) -> dict[str, Any]:
        example_id = str(getattr(example, "id", "") or _as_dict(example).get("id") or "")
        spans = spans_by_example_id.get(example_id, [])
        total, source = _sum_total_tokens(spans)
        if total == 0.0:
            output_dict = _task_output(output)
            fallback = output_dict.get("total_token_usage") or output_dict.get("token_usage")
            if isinstance(fallback, Mapping):
                total = float((fallback.get("total") or 0) or 0)
                source = "output.token_usage.total"
            elif fallback is not None:
                try:
                    total = float(fallback)
                    source = "output.total_token_usage"
                except (TypeError, ValueError):
                    pass
        if total == 0:
            label = "unmeasured"
        elif total < 2000:
            label = "low"
        elif total < 10000:
            label = "medium"
        else:
            label = "high"
        return {"score": float(total), "label": label, "explanation": f"{total:.0f} tokens; {source}"}

    total_token_usage.__name__ = "total_token_usage"
    total_token_usage.__qualname__ = "total_token_usage"
    return total_token_usage


def make_cost(spans_by_example_id: Mapping[str, Sequence[Mapping[str, Any]]]) -> Callable[..., dict[str, Any]]:
    def cost(
        output: dict[str, Any],
        expected: dict[str, Any],
        input: dict[str, Any],
        example: Any = None,
    ) -> dict[str, Any]:
        example_id = str(getattr(example, "id", "") or _as_dict(example).get("id") or "")
        spans = spans_by_example_id.get(example_id, [])
        total, source = _sum_cost(spans)
        if total == 0.0:
            output_dict = _task_output(output)
            fallback = output_dict.get("cost") or output_dict.get("total_cost") or output_dict.get("cost_usd")
            if fallback is not None:
                try:
                    total = float(fallback)
                    source = "output cost field"
                except (TypeError, ValueError):
                    pass
        if total == 0:
            label = "unmeasured"
        elif total < 0.01:
            label = "low"
        elif total < 0.1:
            label = "medium"
        else:
            label = "high"
        return {"score": float(total), "label": label, "explanation": f"${total:.6f}; {source}"}

    cost.__name__ = "cost"
    cost.__qualname__ = "cost"
    return cost


def make_answer_cost() -> Callable[..., dict[str, Any]]:
    def answer_cost(output: dict[str, Any], expected: dict[str, Any], input: dict[str, Any]) -> dict[str, Any]:
        count, source = _count_answer_tokens(_final_answer(output))
        if count == 0:
            label = "empty"
        elif count < 50:
            label = "low"
        elif count < 200:
            label = "medium"
        else:
            label = "high"
        return {"score": float(count), "label": label, "explanation": f"{count} answer token(s); {source}"}

    answer_cost.__name__ = "answer_cost"
    answer_cost.__qualname__ = "answer_cost"
    return answer_cost


def make_turn_count() -> Callable[..., dict[str, Any]]:
    def turn_count(output: dict[str, Any], expected: dict[str, Any], input: dict[str, Any]) -> dict[str, Any]:
        output_dict = _task_output(output)
        raw = output_dict.get("turns") or output_dict.get("turn_count") or 0
        try:
            count = int(raw)
        except (TypeError, ValueError):
            count = 0
        if count == 0:
            label = "zero"
        elif count < 3:
            label = "low"
        elif count < 8:
            label = "medium"
        else:
            label = "high"
        return {"score": float(count), "label": label, "explanation": f"{count} turn(s)"}

    turn_count.__name__ = "turn_count"
    turn_count.__qualname__ = "turn_count"
    return turn_count


def make_elapsed_time() -> Callable[..., dict[str, Any]]:
    def elapsed_time(output: dict[str, Any], expected: dict[str, Any], input: dict[str, Any]) -> dict[str, Any]:
        output_dict = _task_output(output)
        raw = output_dict.get("elapsed_seconds") or output_dict.get("elapsed_time") or output_dict.get("duration")
        try:
            seconds = float(raw)
        except (TypeError, ValueError):
            seconds = 0.0
        if seconds <= 0:
            label = "unmeasured"
        elif seconds < 5:
            label = "fast"
        elif seconds < 30:
            label = "medium"
        else:
            label = "slow"
        return {"score": float(seconds), "label": label, "explanation": f"{seconds:.3f} second(s)"}

    elapsed_time.__name__ = "elapsed_time"
    elapsed_time.__qualname__ = "elapsed_time"
    return elapsed_time

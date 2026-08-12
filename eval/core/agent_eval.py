"""Agent execution-quality evaluator logic."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.eval_common import (
    _final_answer,
    _json_dumps,
    _task_output,
)


def make_task_succeeded() -> Callable[..., dict[str, Any]]:
    def task_succeeded(output: dict[str, Any], expected: dict[str, Any], input: dict[str, Any]) -> dict[str, Any]:
        status = str(_task_output(output).get("status") or "").lower()
        score = 1.0 if status == "ok" else 0.0
        return {
            "score": score,
            "label": "ok" if score else (status or "missing"),
            "explanation": f"status={status or '<missing>'}; original metric only treats exactly 'ok' as success",
        }

    task_succeeded.__name__ = "task_succeeded"
    task_succeeded.__qualname__ = "task_succeeded"
    return task_succeeded


def make_error_absence() -> Callable[..., dict[str, Any]]:
    def error_absence(output: dict[str, Any], expected: dict[str, Any], input: dict[str, Any]) -> dict[str, Any]:
        task_output = _task_output(output)
        error = task_output.get("error")
        status = str(task_output.get("status") or "").lower()
        swe_status = str(task_output.get("swe_status") or "").lower()
        bad_status = status in {"error", "failed", "failure", "timeout", "cancelled", "exception"}
        bad_swe_status = swe_status in {"error", "failed", "failure", "timeout"}
        score = 0.0 if error or bad_status or bad_swe_status else 1.0
        label = "clean" if score else "error"
        explanation = _json_dumps(
            {"status": status or None, "swe_status": swe_status or None, "error": error},
            limit=600,
        )
        return {"score": score, "label": label, "explanation": explanation}

    error_absence.__name__ = "error_absence"
    error_absence.__qualname__ = "error_absence"
    return error_absence


def make_execution_completion() -> Callable[..., dict[str, Any]]:
    def execution_completion(
        output: dict[str, Any], expected: dict[str, Any], input: dict[str, Any]
    ) -> dict[str, Any]:
        task_output = _task_output(output)
        status = str(task_output.get("status") or "").lower()
        final_answer = _final_answer(output).strip()
        resolved = task_output.get("resolved")
        incomplete_statuses = {"running", "timeout", "cancelled", "interrupted", "error", "failed", "failure"}
        completed = bool(resolved is True or status == "ok" or (final_answer and status not in incomplete_statuses))
        return {
            "score": 1.0 if completed else 0.0,
            "label": "complete" if completed else "incomplete",
            "explanation": _json_dumps(
                {
                    "resolved": resolved,
                    "status": status or None,
                    "has_final_answer": bool(final_answer),
                },
                limit=600,
            ),
        }

    execution_completion.__name__ = "execution_completion"
    execution_completion.__qualname__ = "execution_completion"
    return execution_completion

"""Extra Jev scores for metrics that keep their LLM judge.

Each function writes a separate annotation (`<metric>_jev`). The original
metric name stays on the LLM judge.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from core.eval_common import _as_dict, _enrich_output, _instruction, _json_dumps, _unscored
from core.jev_judge import call_systemone
from process_values.tool_eval import (
    _collapse_monitor_clones,
    _locate_loop_windows,
    _loop_call_record,
    _looping_tool_count,
    _parameter_schemas_from_spans,
    _tool_invocation_records,
    _tool_schema_name,
)

_CONSTRAINT = re.compile(r"do not|don't|must|should|only|exactly|required|never", re.I)


def _clip(value: object, limit: int = 400) -> str:
    text = " ".join(_json_dumps(value).split())
    if len(text) <= limit:
        return text
    return text[: limit // 2] + " … " + text[-40:]


def _parameter_block(payload: dict[str, Any]) -> dict[str, Any]:
    function = _as_dict(payload.get("function"))
    for block in (
        payload.get("input_schema"),
        function.get("input_schema"),
        payload.get("parameters"),
        function.get("parameters"),
    ):
        if not isinstance(block, dict):
            continue
        if "properties" in block or "required" in block:
            return block
    return {}


def _schemas(spans: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for payload in _parameter_schemas_from_spans(spans):
        name = _tool_schema_name(payload)
        block = _parameter_block(payload)
        if not name or not block:
            continue
        found[str(name)] = {
            "required": list(block.get("required") or []),
            "properties": {
                key: value.get("type", "string")
                for key, value in _as_dict(block.get("properties")).items()
            },
        }
    return found


def _choice(state: dict[str, Any], instruction: str, criteria: dict[str, str]) -> str:
    payload = call_systemone(
        state=json.dumps(state, ensure_ascii=False),
        questions={
            "label": {
                "type": "choice",
                "instructions": instruction,
                "criteria": criteria,
            }
        },
        timeout=40,
    )
    return str(payload["answers"]["label"].get("choice") or "")


def _noul(state: dict[str, Any] | str, instruction: str) -> float:
    payload = call_systemone(
        state=state if isinstance(state, str) else json.dumps(state, ensure_ascii=False),
        questions={
            "answer": {
                "type": "noul",
                "instructions": instruction,
                "criteria": {"true": "Yes.", "false": "No."},
            }
        },
        timeout=40,
    )
    return float(payload["answers"]["answer"]["noul"])


def make_tool_invocation_jev(
    spans_by_example_id: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> Callable[..., dict[str, Any]]:
    """One call against the trace schema. Extra fields are allowed. Any miss fails the run."""

    spans_map = spans_by_example_id or {}

    def tool_invocation_jev(
        output: dict[str, Any],
        expected: dict[str, Any],
        input: dict[str, Any],
        example: Any = None,
    ) -> dict[str, Any]:
        del expected
        example_id = str(getattr(example, "id", "") or _as_dict(example).get("id") or "")
        spans = spans_map.get(example_id, [])
        enriched = _enrich_output(output, spans)
        records = _tool_invocation_records(enriched)
        if records is None:
            return _unscored("Tool names were recorded without arguments.")
        if not records:
            return _unscored("No tool invocations observed.")
        schemas = _schemas(spans)
        if not schemas:
            return _unscored("No parameter schema was recorded in the trace.")
        incorrect = 0
        for record in records:
            schema = schemas.get(record["name"])
            if not schema:
                incorrect += 1
                continue
            label = _choice(
                {"schema": schema, "call": {"name": record["name"], "arguments": record["arguments"]}},
                "Does this one call satisfy the schema?",
                {
                    "correct": "Every required field is present and types match. Extra fields are allowed.",
                    "incorrect": "A required field is missing or a listed field has the wrong type.",
                },
            )
            if label != "correct":
                incorrect += 1
        if incorrect:
            return {
                "score": 0.0,
                "label": "incorrect",
                "explanation": f"Jev: {incorrect} of {len(records)} calls failed the trace schema.",
            }
        return {
            "score": 1.0,
            "label": "correct",
            "explanation": f"Jev: all {len(records)} calls satisfied the trace schema.",
        }

    return tool_invocation_jev


def make_tool_selection_jev(
    spans_by_example_id: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> Callable[..., dict[str, Any]]:
    """One call at a time: is the tool name on the menu recorded in the trace."""

    spans_map = spans_by_example_id or {}

    def tool_selection_jev(
        output: dict[str, Any],
        expected: dict[str, Any],
        input: dict[str, Any],
        example: Any = None,
    ) -> dict[str, Any]:
        del expected, input
        example_id = str(getattr(example, "id", "") or _as_dict(example).get("id") or "")
        enriched = _enrich_output(output, spans_map.get(example_id, []))
        records = _tool_invocation_records(enriched)
        if records is None or not records:
            return _unscored("No tool invocations to check against the allowed menu.")
        allowed = sorted(_schemas(spans_map.get(example_id, [])))
        if not allowed:
            return _unscored("No tool menu was recorded in the trace.")
        menu = ", ".join(allowed)
        missed = []
        for record in records:
            name = record["name"]
            probability = _noul(
                f"Allowed tools: {menu}. This call uses: {name}.",
                f"Is {name} one of these allowed tools: {menu}?",
            )
            if probability < 0.5:
                missed.append(name)
        if missed:
            return {
                "score": 0.0,
                "label": "incorrect",
                "explanation": f"Jev: names outside the menu: {sorted(set(missed))}.",
            }
        return {
            "score": 1.0,
            "label": "correct",
            "explanation": f"Jev: all {len(records)} calls use a name from {allowed}.",
        }

    return tool_selection_jev


def _explicit_constraints(instruction: str) -> list[str]:
    constraints: list[str] = []
    skipping_tests = False
    for raw in instruction.splitlines():
        line = " ".join(raw.split()).lstrip("-").strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("we will test") or low.startswith("the system will be tested"):
            skipping_tests = True
            continue
        if skipping_tests and (line[0].isdigit() or low.startswith("creating ") or low.startswith("cloning ")):
            continue
        if skipping_tests:
            skipping_tests = False
        if low.startswith("as a sanity check"):
            continue
        if _CONSTRAINT.search(line) or "`/" in line or "/app" in line:
            constraints.append(line)
    seen: set[str] = set()
    kept: list[str] = []
    for line in constraints:
        if line not in seen:
            seen.add(line)
            kept.append(line)
    return kept


def make_plan_constraint_adherence_jev(
    spans_by_example_id: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> Callable[..., dict[str, Any]]:
    """One explicit task sentence at a time, then any violation fails the run."""

    spans_map = spans_by_example_id or {}

    def plan_constraint_adherence_jev(
        output: dict[str, Any],
        expected: dict[str, Any],
        input: dict[str, Any],
        example: Any = None,
    ) -> dict[str, Any]:
        del expected
        constraints = _explicit_constraints(_instruction(input))
        if not constraints:
            return _unscored("No explicit constraint sentence was found in the task.")
        example_id = str(getattr(example, "id", "") or _as_dict(example).get("id") or "")
        enriched = _enrich_output(output, spans_map.get(example_id, []))
        steps = []
        for index, call in enumerate(enriched.get("tool_calls_full") or []):
            item = _as_dict(call)
            args = _as_dict(item.get("arguments"))
            steps.append(
                {
                    "step": index,
                    "tool": item.get("name"),
                    "command": _clip(args.get("command") or args.get("path") or ""),
                }
            )
        violated = 0
        for constraint in constraints:
            label = _choice(
                {"constraint": constraint, "steps": steps},
                "Do these steps violate this explicit constraint?",
                {
                    "adhered": "The steps do not violate the constraint.",
                    "violated": "The steps violate the constraint.",
                },
            )
            if label == "violated":
                violated += 1
        if violated:
            return {
                "score": 0.0,
                "label": "violated",
                "explanation": f"Jev: {violated} of {len(constraints)} explicit constraints were violated.",
            }
        return {
            "score": 1.0,
            "label": "adhered",
            "explanation": f"Jev: all {len(constraints)} explicit constraints were respected.",
        }

    return plan_constraint_adherence_jev


def make_repeated_tool_call_rate_jev(
    spans_by_example_id: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> Callable[..., dict[str, Any]]:
    """Code finds repeated stretches. Jev decides whether they changed the environment."""

    spans_map = spans_by_example_id or {}

    def repeated_tool_call_rate_jev(
        output: dict[str, Any],
        expected: dict[str, Any],
        input: dict[str, Any],
        example: Any = None,
    ) -> dict[str, Any]:
        del expected, input
        example_id = str(getattr(example, "id", "") or _as_dict(example).get("id") or "")
        enriched = _enrich_output(output, spans_map.get(example_id, []))
        raw_calls = [_as_dict(call) for call in (enriched.get("tool_calls_full") or [])]
        records = [record for record in (_loop_call_record(call) for call in raw_calls) if record]
        records = _collapse_monitor_clones(records)
        if not records:
            return _unscored("No tool calls with arguments were available for loop localization.")
        windows = _locate_loop_windows(records)
        if not windows:
            return {
                "score": 0.0,
                "label": "clean",
                "explanation": f"Code found no repeated stretch in {len(records)} calls. Jev was not asked.",
            }
        no_effect = 0
        for window in windows:
            start, end = int(window["start"]), int(window["end"])
            shown = list(range(start, end))
            if len(shown) > 6:
                shown = shown[:3] + shown[-3:]
            rows = [
                {
                    "tool": records[index]["name"],
                    "arguments": _clip(records[index].get("arguments"), 180),
                    "result": _clip(records[index].get("output"), 180),
                }
                for index in shown
            ]
            if _noul({"repeated_calls": rows}, "Are these repeated calls leaving the environment unchanged?") >= 0.5:
                no_effect += 1
        if not no_effect:
            return {
                "score": 0.0,
                "label": "clean",
                "explanation": f"Jev: {len(windows)} repeated stretch(es) still changed the environment.",
            }
        count = _looping_tool_count(records, windows)
        return {
            "score": float(count),
            "label": "looping",
            "explanation": f"Jev: {no_effect} of {len(windows)} repeated stretch(es) did not change the environment.",
        }

    return repeated_tool_call_rate_jev

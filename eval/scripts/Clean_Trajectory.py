"""Clean raw trajectories, evaluate from cleaned evidence, and write back.

Workflow required by `server/TASK_EVAL_CLIENT_API.md`:
1. read experiments and runs through A2E server/client APIs;
2. fetch trace spans through `client.spans.get_spans(project_identifier=..., trace_ids=[...])`;
3. call GPT-5.5 to turn raw spans into structured `trajectory_evidence`;
4. evaluate metrics from that cleaned evidence;
5. write all results back with `evaluate_experiment`.

The raw A2E database is never queried or mutated directly.
"""

from __future__ import annotations

import argparse
import inspect
import json
import logging
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

EVAL_ROOT = Path(__file__).resolve().parents[1]
if str(EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(EVAL_ROOT))

from a2e.client import Client
from a2e.client.experiments import evaluate_experiment, get_experiment
from a2e.client.resources.experiments.evaluators import create_evaluator
from a2e.evals.llm import LLM

from scripts import terminal_bench_eval_writeback as base

LOGGER = logging.getLogger("Clean_Trajectory")

DEFAULT_METRICS = (
    "trajectory_evidence",
    "plan_grade",
    "plan_goal_alignment",
    "plan_completeness",
    "plan_constraint_adherence",
    "reasoning_coherence",
    "plan_hallucination",
    "hallucination",
    "conciseness",
    "tool_recall",
    "correctness",
    "total_token_usage",
    "cost",
)

PLAN_EVIDENCE_METRICS: dict[str, dict[str, Any]] = {
    "plan_grade": {
        "definition": (
            "Grade plan quality following Agent Planning Benchmark (APB) Plan Grade. Evaluate "
            "functional viability and logical soundness, not surface similarity to a reference. "
            "Detect APB E1-E6 errors independently. Use perfect/1.0 when all errors are absent; "
            "very_good/0.8 for an almost perfect plan with only a minor non-critical issue; "
            "mostly_correct/0.6 when the main flow is captured but one key component is missing "
            "or flawed; partially_correct/0.4 when some correct steps exist but the overall "
            "sequence is wrong; mostly_incorrect/0.2 when deeply flawed with limited merit; "
            "failed/0.0 for zero logical merit, complete hallucination, or complete goal misunderstanding."
        ),
        "choices": (
            "perfect",
            "very_good",
            "mostly_correct",
            "partially_correct",
            "mostly_incorrect",
            "failed",
        ),
        "positive": "perfect",
        "score_map": {
            "perfect": 1.0,
            "very_good": 0.8,
            "mostly_correct": 0.6,
            "partially_correct": 0.4,
            "mostly_incorrect": 0.2,
            "failed": 0.0,
        },
    },
    "plan_goal_alignment": {
        "definition": (
            "Judge the inverse of APB E1_GOAL_UNDERSTANDING. Label aligned if the plan preserves "
            "the user's core intent; label misaligned if it fundamentally misunderstands, deviates "
            "from, or contradicts the query objective. Do not penalize different valid solution paths."
        ),
        "choices": ("aligned", "misaligned"),
        "positive": "aligned",
    },
    "plan_completeness": {
        "definition": (
            "Judge the inverse of APB E2_TASK_COMPLETENESS / E2_PREMATURE_CONCLUSION. Label complete "
            "if the plan covers all required subtasks and does not conclude before necessary evidence "
            "or actions are obtained; label incomplete if required subtasks are missing or it stops early."
        ),
        "choices": ("complete", "incomplete"),
        "positive": "complete",
    },
    "plan_constraint_adherence": {
        "definition": (
            "Judge the inverse of APB E3_CONSTRAINT_VIOLATION. Label adhered if the plan respects all "
            "explicit user, system, format, allowed-tool, time, source, method, scope, and safety "
            "constraints; label violated if any explicit constraint is violated."
        ),
        "choices": ("adhered", "violated"),
        "positive": "adhered",
    },
    "reasoning_coherence": {
        "definition": (
            "Judge the inverse of APB E4_LOGICAL_DEFECT. Label coherent when each step has required "
            "premises, uses available evidence correctly, does not require unavailable data/results, "
            "does not ignore obtained data, and avoids circular or risky reasoning. Label logic_error "
            "when causal errors, ordering errors, missing prerequisites, unsupported dependencies, "
            "or circular logic appear."
        ),
        "choices": ("coherent", "logic_error"),
        "positive": "coherent",
    },
    "plan_hallucination": {
        "definition": (
            "Judge the inverse of APB E6_HALLUCINATION_ERROR. Label grounded if the plan does not call "
            "non-existent tools, reference non-existent data, invent unavailable intermediate results, "
            "or state factual claims contrary to context. Label hallucinated if it uses a non-existent "
            "tool, fabricates data/results, or relies on evidence unavailable at that step."
        ),
        "choices": ("grounded", "hallucinated"),
        "positive": "grounded",
    },
}

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
_SECRET_RE = re.compile(r"\b(?:sk|pk|ghp|hf)_[A-Za-z0-9_\-]{12,}\b")
_SECURITY_TERMS = (
    "crack",
    "password",
    "hash",
    "exploit",
    "vulnerability",
    "secret",
    "private key",
    "token",
    "credential",
)


def _safe_text(value: Any, *, limit: int = 500) -> str:
    text = str(value or "")
    text = _SECRET_RE.sub("[REDACTED_SECRET]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit] + "..."


def _command_hint(text: str) -> str:
    lowered = text.lower()
    hints: list[str] = []
    for name, needles in (
        ("git", ("git ",)),
        ("python", ("python", "pytest", "pip ", "uv ")),
        ("node", ("npm ", "node ", "pnpm ", "yarn ")),
        ("filesystem", ("ls ", "cat ", "sed ", "grep ", "find ", "cp ", "mv ", "mkdir ", "touch ")),
        ("archive", ("tar ", "zip ", "unzip ", "gzip ", "bzip", "xz ")),
        ("network", ("curl ", "wget ", "http://", "https://")),
        ("build/test", ("make ", "cmake", "cargo ", "go test", "mvn ", "gradle")),
        ("database", ("sqlite", "psql", "mysql")),
        ("security-related", ("hash", "crack", "password", "openssl", "key", "secret")),
    ):
        if any(needle in lowered for needle in needles):
            hints.append(name)
    return ", ".join(dict.fromkeys(hints)) or "general shell/action"


def _contains_security_terms(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in _SECURITY_TERMS)


def _safe_dataset_field(value: Any, *, field_name: str) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _safe_dataset_field(item, field_name=str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_dataset_field(item, field_name=field_name) for item in value[:20]]
    if isinstance(value, str):
        text = _safe_text(value, limit=1000)
        if _contains_security_terms(text):
            return {
                "redacted": True,
                "field": field_name,
                "length": len(value),
                "category_hint": _command_hint(text),
            }
        return text
    return value


def _safe_argument_value(key: str, value: Any) -> Any:
    lowered = key.lower()
    if isinstance(value, Mapping):
        return {str(k): _safe_argument_value(str(k), v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_argument_value(key, item) for item in value[:20]]
    if lowered in {"cmd", "command", "script", "code", "stdin", "input", "query"}:
        text = _safe_text(value, limit=240)
        return {
            "redacted": True,
            "length": len(str(value or "")),
            "category_hint": _command_hint(text),
        }
    if isinstance(value, str):
        return _safe_text(value, limit=240)
    return value


def _safe_tool_call(call: Mapping[str, Any]) -> dict[str, Any]:
    arguments = base._as_dict(call.get("arguments"))
    result = call.get("result")
    result_dict = base._as_dict(result)
    safe_result: dict[str, Any]
    if result_dict:
        safe_result = {
            key: _safe_argument_value(str(key), value)
            for key, value in result_dict.items()
            if str(key).lower() in {"exit_code", "status", "error", "stderr", "stdout", "output", "result"}
        }
    elif result is None:
        safe_result = {}
    else:
        safe_result = {"summary": _safe_text(result, limit=240)}
    return {
        "name": _safe_text(call.get("name"), limit=80),
        "arguments": {str(k): _safe_argument_value(str(k), v) for k, v in arguments.items()},
        "result": safe_result,
    }


def _json_loads_best_effort(text: str) -> dict[str, Any]:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_RE.search(text)
        if not match:
            return {
                "cleaning_error": "model did not return JSON",
                "raw_model_output": text[:2000],
            }
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            return {
                "cleaning_error": f"invalid JSON: {exc}",
                "raw_model_output": text[:2000],
            }
    return obj if isinstance(obj, dict) else {"cleaning_error": "JSON root was not an object"}


def _compact_tool_history(output: Mapping[str, Any], spans: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    enriched = base._enrich_output(output, spans)
    full = enriched.get("tool_calls_full") or []
    if full:
        cleaned: list[dict[str, Any]] = []
        for call in full:
            call_dict = base._as_dict(call)
            cleaned.append(_safe_tool_call(call_dict))
        return cleaned
    return [{"name": name, "arguments": {}, "result": None} for name in enriched.get("tool_calls") or []]


def _build_raw_view(
    *,
    example: Mapping[str, Any],
    run: Mapping[str, Any],
    spans: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    output = base._task_output(run.get("output"))
    return {
        "example_id": example.get("id"),
        "task_input": _safe_dataset_field(example.get("input"), field_name="input"),
        "expected": _safe_dataset_field(example.get("output"), field_name="expected"),
        "metadata": _safe_dataset_field(example.get("metadata"), field_name="metadata"),
        "task_output": {
            "status": output.get("status"),
            "resolved": output.get("resolved"),
            "swe_status": output.get("swe_status"),
            "error": _safe_text(output.get("error"), limit=500),
            "turns": output.get("turns"),
            "final_answer": _safe_text(output.get("final_answer"), limit=2000),
            "model_patch": {
                "present": bool(output.get("model_patch")),
                "length": len(str(output.get("model_patch") or "")),
            },
        },
        "tool_history": _compact_tool_history(output, spans),
        "trace_id": run.get("trace_id"),
    }


def _clean_trajectory(llm: LLM, raw_view: Mapping[str, Any]) -> dict[str, Any]:
    prompt = (
        "You are cleaning an AI agent trajectory for later evaluation.\n"
        "Use ONLY the provided raw facts. Do not invent facts. If a fact is missing, say unknown.\n"
        "Return strict JSON only with these keys:\n"
        "{\n"
        '  "task_goal": string,\n'
        '  "terminal_bench_status": {"resolved": boolean|null, "status": string|null, '
        '"error": string|null, "swe_status": string|null},\n'
        '  "files_created_or_modified": [{"path": string, "evidence": string}],\n'
        '  "commands_run": [{"command": string, "exit_code": integer|null, "purpose": string}],\n'
        '  "verification_attempts": [{"command_or_action": string, "passed": boolean|null, '
        '"evidence": string}],\n'
        '  "tool_use_summary": {"necessary_steps_covered": string, "redundant_or_failed_steps": string, '
        '"tool_recall_label": "complete|partial|incomplete", "tool_recall_score": number},\n'
        '  "plan_summary": {"parsimony_label": "parsimonious|some_waste|over_planned", '
        '"evidence": string},\n'
        '  "evidence_for_success": [string],\n'
        '  "evidence_against_success": [string],\n'
        '  "final_answer_summary": string,\n'
        '  "uncertainties": [string]\n'
        "}\n\n"
        "Raw trajectory facts:\n"
        f"{base._json_dumps(raw_view, limit=24000)}"
    )
    try:
        text = llm.generate_text(prompt=prompt)
    except Exception as exc:
        LOGGER.warning("trajectory cleaning failed for example_id=%s: %s", raw_view.get("example_id"), exc)
        return {
            "cleaning_error": str(exc),
            "raw_trace_id": raw_view.get("trace_id"),
            "example_id": raw_view.get("example_id"),
            "task_goal": _safe_text(raw_view.get("task_input"), limit=1000),
            "terminal_bench_status": base._as_dict(raw_view.get("task_output")),
            "evidence_for_success": [],
            "evidence_against_success": ["LLM trajectory cleaning failed; use task output status only."],
            "uncertainties": ["Cleaned trajectory unavailable due to LLM/provider rejection or error."],
            "tool_use_summary": {
                "necessary_steps_covered": "unknown",
                "redundant_or_failed_steps": "unknown",
                "tool_recall_label": "unknown",
                "tool_recall_score": 0.0,
            },
            "plan_summary": {
                "parsimony_label": "over_planned",
                "evidence": "Cleaned trajectory unavailable.",
            },
            "final_answer_summary": _safe_text(base._as_dict(raw_view.get("task_output")).get("final_answer")),
        }
    evidence = _json_loads_best_effort(text or "")
    evidence.setdefault("raw_trace_id", raw_view.get("trace_id"))
    evidence.setdefault("example_id", raw_view.get("example_id"))
    return evidence


def _precompute_evidence(
    *,
    client: Client,
    experiment: Mapping[str, Any],
    spans_by_example_id: Mapping[str, Sequence[Mapping[str, Any]]],
    llm: LLM,
    timeout: int,
) -> dict[str, dict[str, Any]]:
    dataset = client.datasets.get_dataset(
        dataset=experiment["dataset_id"],
        version_id=experiment["dataset_version_id"],
        timeout=timeout,
    )
    examples_by_id = {example["id"]: example for example in dataset.examples}
    evidence_by_example_id: dict[str, dict[str, Any]] = {}
    for run in experiment.get("task_runs", []):
        run_dict = base._as_dict(run)
        example_id = str(run_dict.get("dataset_example_id") or "")
        example = examples_by_id.get(example_id)
        if not example:
            LOGGER.warning("missing dataset example for run id=%s", run_dict.get("id"))
            continue
        raw_view = _build_raw_view(
            example=example,
            run=run_dict,
            spans=spans_by_example_id.get(example_id, []),
        )
        LOGGER.info("cleaning trajectory for example_id=%s", example_id)
        evidence_by_example_id[example_id] = _clean_trajectory(llm, raw_view)
    return evidence_by_example_id


def _evidence_for(example: Any, evidence_by_example_id: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    example_id = str(getattr(example, "id", "") or base._as_dict(example).get("id") or "")
    return evidence_by_example_id.get(example_id, {})


def make_trajectory_evidence(
    evidence_by_example_id: Mapping[str, dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    def trajectory_evidence(example: Any = None, **_: Any) -> dict[str, Any]:
        evidence = _evidence_for(example, evidence_by_example_id)
        has_error = bool(evidence.get("cleaning_error"))
        return {
            "score": 0.0 if has_error else 1.0,
            "label": "cleaning_error" if has_error else "cleaned",
            "explanation": base._json_dumps(
                {
                    "task_goal": evidence.get("task_goal"),
                    "terminal_bench_status": evidence.get("terminal_bench_status"),
                    "evidence_for_success": evidence.get("evidence_for_success", [])[:3],
                    "evidence_against_success": evidence.get("evidence_against_success", [])[:3],
                    "uncertainties": evidence.get("uncertainties", [])[:3],
                },
                limit=1000,
            ),
            "metadata": {"trajectory_evidence": evidence},
        }

    trajectory_evidence.__name__ = "trajectory_evidence"
    trajectory_evidence.__qualname__ = "trajectory_evidence"
    return trajectory_evidence


def _judge_from_evidence(
    *,
    metric_name: str,
    definition: str,
    choices: Sequence[str],
    positive: str,
    llm: LLM,
    evidence_by_example_id: Mapping[str, dict[str, Any]],
    score_map: Mapping[str, float] | None = None,
) -> Callable[..., dict[str, Any]]:
    def evaluator(output: dict[str, Any], input: dict[str, Any], example: Any = None, **_: Any) -> dict[str, Any]:
        evidence = _evidence_for(example, evidence_by_example_id)
        prompt = base._build_text_prompt(
            metric_name=metric_name,
            definition=definition,
            choices=choices,
            positive=positive,
            context={
                "Question": base._instruction(input),
                "Clean trajectory evidence": base._json_dumps(evidence, limit=12000),
                "Task output": base._json_dumps(base._task_output(output), limit=6000),
            },
        )
        result = base._text_judge(llm, prompt, choices, positive)
        label = str(result.get("label") or "")
        if score_map and label in score_map:
            result["score"] = float(score_map[label])
        result["metadata"] = {"trajectory_evidence": evidence}
        return result

    evaluator.__name__ = metric_name
    evaluator.__qualname__ = metric_name
    return evaluator


def make_tool_recall_from_evidence(
    evidence_by_example_id: Mapping[str, dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    def tool_recall(example: Any = None, **_: Any) -> dict[str, Any]:
        evidence = _evidence_for(example, evidence_by_example_id)
        summary = base._as_dict(evidence.get("tool_use_summary"))
        raw_score = summary.get("tool_recall_score")
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = 0.0
        label = str(summary.get("tool_recall_label") or "unknown")
        return {
            "score": max(0.0, min(1.0, score)),
            "label": label,
            "explanation": base._json_dumps(
                {
                    "necessary_steps_covered": summary.get("necessary_steps_covered"),
                    "redundant_or_failed_steps": summary.get("redundant_or_failed_steps"),
                },
                limit=1000,
            ),
            "metadata": {"trajectory_evidence": evidence},
        }

    tool_recall.__name__ = "tool_recall"
    tool_recall.__qualname__ = "tool_recall"
    return tool_recall


def _build_cleaned_evaluators(
    *,
    metric_names: Sequence[str],
    evidence_by_example_id: Mapping[str, dict[str, Any]],
    spans_by_example_id: Mapping[str, Sequence[Mapping[str, Any]]],
    llm: LLM,
    score_marker_suffix: float = 0.0,
) -> dict[str, Callable[..., Any]]:
    evaluators: dict[str, Callable[..., Any]] = {}
    for metric in metric_names:
        if metric == "trajectory_evidence":
            fn = make_trajectory_evidence(evidence_by_example_id)
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _with_score_marker(fn, score_marker_suffix)
            )
        elif metric in PLAN_EVIDENCE_METRICS:
            spec = PLAN_EVIDENCE_METRICS[metric]
            fn = _judge_from_evidence(
                metric_name=metric,
                definition=str(spec["definition"]),
                choices=tuple(spec["choices"]),
                positive=str(spec["positive"]),
                llm=llm,
                evidence_by_example_id=evidence_by_example_id,
                score_map=base._as_dict(spec.get("score_map")),
            )
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _with_score_marker(fn, score_marker_suffix)
            )
        elif metric == "tool_recall":
            fn = make_tool_recall_from_evidence(evidence_by_example_id)
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _with_score_marker(fn, score_marker_suffix)
            )
        elif metric == "correctness":
            fn = _judge_from_evidence(
                metric_name="correctness",
                definition=(
                    "Judge whether the task was actually solved. For terminal-bench, prioritize "
                    "`resolved`, verification attempts, files/artifacts, errors, and evidence in "
                    "the cleaned trajectory over final-answer wording."
                ),
                choices=("correct", "incorrect"),
                positive="correct",
                llm=llm,
                evidence_by_example_id=evidence_by_example_id,
            )
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _with_score_marker(fn, score_marker_suffix)
            )
        elif metric == "hallucination":
            fn = _judge_from_evidence(
                metric_name="hallucination",
                definition=(
                    "Judge whether the final answer or claimed actions are faithful to the cleaned "
                    "trajectory evidence. Label faithful means no hallucination."
                ),
                choices=("faithful", "unfaithful"),
                positive="faithful",
                llm=llm,
                evidence_by_example_id=evidence_by_example_id,
            )
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _with_score_marker(fn, score_marker_suffix)
            )
        elif metric == "conciseness":
            fn = _judge_from_evidence(
                metric_name="conciseness",
                definition="Judge whether the final response is concise without unnecessary text.",
                choices=("concise", "verbose"),
                positive="concise",
                llm=llm,
                evidence_by_example_id=evidence_by_example_id,
            )
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _with_score_marker(fn, score_marker_suffix)
            )
        elif metric == "total_token_usage":
            fn = base.make_total_token_usage(spans_by_example_id)
            evaluators[metric] = create_evaluator(kind="CODE", name=metric)(
                _with_score_marker(fn, score_marker_suffix)
            )
        elif metric == "cost":
            fn = base.make_cost(spans_by_example_id)
            evaluators[metric] = create_evaluator(kind="CODE", name=metric)(
                _with_score_marker(fn, score_marker_suffix)
            )
        else:
            raise ValueError(f"Unsupported metric: {metric}")
    return evaluators


def _with_score_marker(evaluator: Callable[..., Any], score_marker_suffix: float) -> Callable[..., Any]:
    if not score_marker_suffix:
        return evaluator
    signature = inspect.signature(evaluator)
    accepts_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values())
    accepted_names = set(signature.parameters)

    def marked_evaluator(
        output: Any = None,
        input: Any = None,
        expected: Any = None,
        reference: Any = None,
        metadata: Any = None,
        example: Any = None,
    ) -> Any:
        payload = {
            "output": output,
            "input": input,
            "expected": expected,
            "reference": reference,
            "metadata": metadata,
            "example": example,
        }
        if accepts_kwargs:
            result = evaluator(**payload)
        else:
            result = evaluator(**{name: value for name, value in payload.items() if name in accepted_names})
        if not isinstance(result, dict) or "score" not in result:
            return result
        try:
            original_score = float(result["score"])
        except (TypeError, ValueError):
            return result
        marked = dict(result)
        marked["score"] = original_score + score_marker_suffix
        metadata = dict(base._as_dict(marked.get("metadata")))
        metadata["unmarked_score"] = original_score
        metadata["score_marker_suffix"] = score_marker_suffix
        marked["metadata"] = metadata
        return marked

    marked_evaluator.__name__ = evaluator.__name__
    marked_evaluator.__qualname__ = evaluator.__qualname__
    return marked_evaluator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean A2E trajectories with GPT-5.5, evaluate from cleaned evidence, write back."
    )
    parser.add_argument("--base-url", default=os.getenv("A2E_BASE_URL", "http://localhost:6006"))
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--metrics", default=",".join(DEFAULT_METRICS))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=360)
    parser.add_argument("--span-limit", type=int, default=2000)
    parser.add_argument("--llm-provider", default=os.getenv("A2E_EVAL_LLM_PROVIDER", "openai"))
    parser.add_argument("--llm-model", default=os.getenv("A2E_EVAL_LLM_MODEL", "gpt-5.5"))
    parser.add_argument("--llm-base-url", default=os.getenv("OPENAI_API_BASE"))
    parser.add_argument("--llm-api-key", default=os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--llm-timeout", type=float, default=240.0)
    parser.add_argument(
        "--score-marker-suffix",
        type=float,
        default=0.0,
        help="Add this numeric suffix to every evaluator score and store the unmarked score in metadata.",
    )
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(message)s")
    metric_names = [name.strip() for name in args.metrics.split(",") if name.strip()]

    client = Client(base_url=args.base_url)
    header = client.experiments.get(experiment_id=args.experiment_id)
    project_name = args.project_name or header.get("project_name")
    experiment = get_experiment(experiment_id=args.experiment_id, client=client)

    if not args.force:
        metric_names = base._select_metrics(experiment, metric_names, force=False)
    if not metric_names:
        LOGGER.info("No metrics selected; requested annotations already exist.")
        return

    spans_by_example_id = base._fetch_spans_by_example_id(
        client,
        experiment,
        project_name=project_name,
        limit=args.span_limit,
        timeout=args.timeout,
    )
    llm = base._create_llm(args)
    evidence_by_example_id = _precompute_evidence(
        client=client,
        experiment=experiment,
        spans_by_example_id=spans_by_example_id,
        llm=llm,
        timeout=args.timeout,
    )
    evaluators = _build_cleaned_evaluators(
        metric_names=metric_names,
        evidence_by_example_id=evidence_by_example_id,
        spans_by_example_id=spans_by_example_id,
        llm=llm,
        score_marker_suffix=args.score_marker_suffix,
    )

    LOGGER.info(
        "evaluating from cleaned evidence experiment_id=%s project=%s metrics=%s dry_run=%s",
        args.experiment_id,
        project_name,
        ",".join(metric_names),
        args.dry_run,
    )
    evaluated = evaluate_experiment(
        experiment=experiment,
        evaluators=evaluators,
        dry_run=args.dry_run,
        print_summary=True,
        timeout=args.timeout,
        client=client,
    )
    LOGGER.info("done: total evaluation runs now=%s", len(evaluated.get("evaluation_runs", [])))


if __name__ == "__main__":
    main()

"""Pull experiment data from A2E server, evaluate, and write annotations back.

Metric scoring lives in:
- core/agent_eval.py
- process_values/
- result_values/

This file owns only server/client orchestration as required by
`server/TASK_EVAL_CLIENT_API.md`.
"""

from __future__ import annotations

import argparse
import logging
import os
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any

from a2e.client import Client
from a2e.client.experiments import evaluate_experiment, get_experiment
from a2e.client.resources.experiments.evaluators import create_evaluator
from a2e.evals.llm import LLM

from result_values.efficiency_eval import (
    make_answer_cost,
    make_cost,
    make_elapsed_time,
    make_total_token_usage,
    make_turn_count,
)
from result_values.safety_eval import (
    make_evidence_consistency,
    make_evaluation_awareness,
    make_faithfulness,
    make_failure_transparency,
    make_hallucination,
    make_harmful_action,
    make_overclaiming,
    make_privacy_leakage,
    make_prompt_injection_resilience,
    make_refusal,
    make_safety,
    make_sandbox_escape_risk,
    make_tool_approval_compliance,
    make_tool_response_handling_safety,
    make_trustworthiness,
    make_unauthorized_action,
    make_uncertainty_calibration,
)
from core.agent_eval import (
    make_error_absence,
    make_execution_completion,
    make_task_succeeded,
)
from process_values.correct_eval import (
    make_correctness,
    make_instruction_following,
    make_llm_judge,
)
from core.eval_common import _as_dict, _make_enriching_llm_evaluator
from process_values.plan_eval import (
    make_plan_completeness,
    make_plan_constraint_adherence,
    make_plan_goal_alignment,
    make_plan_grade,
    make_plan_hallucination,
    make_reasoning_coherence,
)
from process_values.skill_eval import make_conciseness
from process_values.tool_eval import (
    make_self_correction_rate,
    make_tool_call_count,
    make_tool_hallucination,
    make_tool_invocation,
    make_tool_recall,
    make_tool_selection,
)
from core.metric_groups import ALL_METRICS

LOGGER = logging.getLogger("deal_server")

TARGET_METRICS = ALL_METRICS

LLM_METRICS = {
    "conciseness",
    "correctness",
    "evidence_consistency",
    "faithfulness",
    "failure_transparency",
    "instruction_following",
    "llm_judge",
    "hallucination",
    "harmful_action",
    "overclaiming",
    "privacy_leakage",
    "prompt_injection_resilience",
    "refusal",
    "safety",
    "sandbox_escape_risk",
    "tool_approval_compliance",
    "tool_response_handling_safety",
    "tool_invocation",
    "tool_recall",
    "tool_selection",
    "trustworthiness",
    "unauthorized_action",
    "uncertainty_calibration",
    "evaluation_awareness",
    "reasoning_coherence",
    "plan_grade",
    "plan_goal_alignment",
    "plan_completeness",
    "plan_constraint_adherence",
    "plan_hallucination",
}


def _create_llm(args: argparse.Namespace) -> LLM:
    kwargs: dict[str, Any] = {}
    if args.llm_api_key:
        kwargs["api_key"] = args.llm_api_key
    if args.llm_base_url:
        kwargs["base_url"] = args.llm_base_url
    if args.llm_timeout:
        kwargs["sync_client_kwargs"] = {"timeout": float(args.llm_timeout)}
        kwargs["async_client_kwargs"] = {"timeout": float(args.llm_timeout)}
    return LLM(provider=args.llm_provider, model=args.llm_model, **kwargs)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value or "")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.min


def _discover_experiment_id(
    client: Client,
    *,
    dataset_name: str | None,
    experiment_name: str | None,
    timeout: int,
) -> str:
    candidates: list[dict[str, Any]] = []
    for dataset in client.datasets.list(timeout=timeout):
        dataset_id = str(dataset["id"])
        current_dataset_name = str(dataset.get("name") or "")
        if dataset_name and dataset_name not in current_dataset_name:
            continue
        for experiment in client.experiments.list(dataset_id=dataset_id, timeout=timeout):
            current_experiment_name = str(experiment.get("name") or "")
            if experiment_name and experiment_name not in current_experiment_name:
                continue
            candidates.append(dict(experiment))
    if not candidates:
        raise RuntimeError(
            "No experiment found. Pass --experiment-id, or adjust --dataset-name/--experiment-name."
        )
    candidates.sort(key=lambda item: _parse_datetime(item.get("created_at")), reverse=True)
    selected = candidates[0]
    LOGGER.info(
        "selected experiment id=%s name=%s created_at=%s",
        selected.get("id"),
        selected.get("name"),
        selected.get("created_at"),
    )
    return str(selected["id"])


def _completed_metric_names_by_run(experiment: Mapping[str, Any]) -> dict[str, set[str]]:
    names: dict[str, set[str]] = defaultdict(set)
    for eval_run in experiment.get("evaluation_runs", []):
        run_id = str(getattr(eval_run, "experiment_run_id", "") or "")
        name = str(getattr(eval_run, "name", "") or "")
        if run_id and name:
            names[run_id].add(name)
    return names


def _select_metrics(
    experiment: Mapping[str, Any],
    requested: Sequence[str],
    *,
    force: bool,
) -> list[str]:
    if force:
        return list(requested)
    task_run_ids = [str(run.get("id")) for run in experiment.get("task_runs", []) if run.get("id")]
    completed_by_run = _completed_metric_names_by_run(experiment)
    selected: list[str] = []
    for metric in requested:
        if task_run_ids and all(metric in completed_by_run.get(run_id, set()) for run_id in task_run_ids):
            LOGGER.info("skip metric %s because all runs already have it", metric)
            continue
        selected.append(metric)
    return selected


def _fetch_spans_by_example_id(
    client: Client,
    experiment: Mapping[str, Any],
    *,
    project_name: str | None,
    limit: int,
    timeout: int,
) -> dict[str, list[Mapping[str, Any]]]:
    if not project_name:
        LOGGER.warning("project_name is missing; span-backed metrics will use task output only")
        return {}

    spans_by_example_id: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for run in experiment.get("task_runs", []):
        run_dict = _as_dict(run)
        trace_id = run_dict.get("trace_id")
        example_id = run_dict.get("dataset_example_id")
        if not trace_id or not example_id:
            continue
        spans = client.spans.get_spans(
            project_identifier=project_name,
            trace_ids=[str(trace_id)],
            limit=limit,
            timeout=timeout,
        )
        spans_by_example_id[str(example_id)].extend(spans)
    return dict(spans_by_example_id)


def _build_evaluators(
    metric_names: Sequence[str],
    *,
    llm: LLM | None,
    spans_by_example_id: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Callable[..., Any]]:
    evaluators: dict[str, Callable[..., Any]] = {}
    for metric in metric_names:
        if metric == "plan_grade":
            if llm is None:
                raise ValueError("plan_grade requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_plan_grade(llm), spans_by_example_id)
            )
        elif metric == "plan_goal_alignment":
            if llm is None:
                raise ValueError("plan_goal_alignment requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_plan_goal_alignment(llm), spans_by_example_id)
            )
        elif metric == "plan_completeness":
            if llm is None:
                raise ValueError("plan_completeness requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_plan_completeness(llm), spans_by_example_id)
            )
        elif metric == "plan_constraint_adherence":
            if llm is None:
                raise ValueError("plan_constraint_adherence requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_plan_constraint_adherence(llm), spans_by_example_id)
            )
        elif metric == "reasoning_coherence":
            if llm is None:
                raise ValueError("reasoning_coherence requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_reasoning_coherence(llm), spans_by_example_id)
            )
        elif metric == "plan_hallucination":
            if llm is None:
                raise ValueError("plan_hallucination requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_plan_hallucination(llm), spans_by_example_id)
            )
        elif metric == "tool_recall":
            if llm is None:
                raise ValueError("tool_recall requires an LLM for terminal-bench fallback")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                make_tool_recall(spans_by_example_id, llm=llm)
            )
        elif metric == "tool_call_count":
            evaluators[metric] = create_evaluator(kind="CODE", name=metric)(
                make_tool_call_count(spans_by_example_id)
            )
        elif metric == "tool_hallucination":
            evaluators[metric] = create_evaluator(kind="CODE", name=metric)(
                make_tool_hallucination(spans_by_example_id)
            )
        elif metric == "self_correction_rate":
            evaluators[metric] = create_evaluator(kind="CODE", name=metric)(
                make_self_correction_rate(spans_by_example_id)
            )
        elif metric == "total_token_usage":
            evaluators[metric] = create_evaluator(kind="CODE", name=metric)(
                make_total_token_usage(spans_by_example_id)
            )
        elif metric == "cost":
            evaluators[metric] = create_evaluator(kind="CODE", name=metric)(
                make_cost(spans_by_example_id)
            )
        elif metric == "answer_cost":
            evaluators[metric] = create_evaluator(kind="CODE", name=metric)(make_answer_cost())
        elif metric == "turn_count":
            evaluators[metric] = create_evaluator(kind="CODE", name=metric)(make_turn_count())
        elif metric == "elapsed_time":
            evaluators[metric] = create_evaluator(kind="CODE", name=metric)(make_elapsed_time())
        elif metric == "error_absence":
            evaluators[metric] = create_evaluator(kind="CODE", name=metric)(make_error_absence())
        elif metric == "execution_completion":
            evaluators[metric] = create_evaluator(kind="CODE", name=metric)(make_execution_completion())
        elif metric == "task_succeeded":
            evaluators[metric] = create_evaluator(kind="CODE", name=metric)(make_task_succeeded())
        elif metric == "correctness":
            if llm is None:
                raise ValueError("correctness requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_correctness(llm), spans_by_example_id)
            )
        elif metric == "llm_judge":
            if llm is None:
                raise ValueError("llm_judge requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_llm_judge(llm), spans_by_example_id)
            )
        elif metric == "instruction_following":
            if llm is None:
                raise ValueError("instruction_following requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_instruction_following(llm), spans_by_example_id)
            )
        elif metric == "conciseness":
            if llm is None:
                raise ValueError("conciseness requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_conciseness(llm), spans_by_example_id)
            )
        elif metric == "hallucination":
            if llm is None:
                raise ValueError("hallucination requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_hallucination(llm), spans_by_example_id)
            )
        elif metric == "faithfulness":
            if llm is None:
                raise ValueError("faithfulness requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_faithfulness(llm), spans_by_example_id)
            )
        elif metric == "refusal":
            if llm is None:
                raise ValueError("refusal requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_refusal(llm), spans_by_example_id)
            )
        elif metric == "tool_selection":
            if llm is None:
                raise ValueError("tool_selection requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_tool_selection(llm), spans_by_example_id)
            )
        elif metric == "tool_invocation":
            if llm is None:
                raise ValueError("tool_invocation requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_tool_invocation(llm), spans_by_example_id)
            )
        elif metric == "evidence_consistency":
            if llm is None:
                raise ValueError("evidence_consistency requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_evidence_consistency(llm), spans_by_example_id)
            )
        elif metric == "privacy_leakage":
            if llm is None:
                raise ValueError("privacy_leakage requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_privacy_leakage(llm), spans_by_example_id)
            )
        elif metric == "unauthorized_action":
            if llm is None:
                raise ValueError("unauthorized_action requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_unauthorized_action(llm), spans_by_example_id)
            )
        elif metric == "harmful_action":
            if llm is None:
                raise ValueError("harmful_action requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_harmful_action(llm), spans_by_example_id)
            )
        elif metric == "overclaiming":
            if llm is None:
                raise ValueError("overclaiming requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_overclaiming(llm), spans_by_example_id)
            )
        elif metric == "uncertainty_calibration":
            if llm is None:
                raise ValueError("uncertainty_calibration requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_uncertainty_calibration(llm), spans_by_example_id)
            )
        elif metric == "failure_transparency":
            if llm is None:
                raise ValueError("failure_transparency requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_failure_transparency(llm), spans_by_example_id)
            )
        elif metric == "prompt_injection_resilience":
            if llm is None:
                raise ValueError(
                    "prompt_injection_resilience requires an LLM; set --llm-provider and --llm-model"
                )
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(
                    metric, make_prompt_injection_resilience(llm), spans_by_example_id
                )
            )
        elif metric == "tool_response_handling_safety":
            if llm is None:
                raise ValueError(
                    "tool_response_handling_safety requires an LLM; set --llm-provider and --llm-model"
                )
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(
                    metric, make_tool_response_handling_safety(llm), spans_by_example_id
                )
            )
        elif metric == "sandbox_escape_risk":
            if llm is None:
                raise ValueError("sandbox_escape_risk requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_sandbox_escape_risk(llm), spans_by_example_id)
            )
        elif metric == "tool_approval_compliance":
            if llm is None:
                raise ValueError(
                    "tool_approval_compliance requires an LLM; set --llm-provider and --llm-model"
                )
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(
                    metric, make_tool_approval_compliance(llm), spans_by_example_id
                )
            )
        elif metric == "evaluation_awareness":
            if llm is None:
                raise ValueError("evaluation_awareness requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_evaluation_awareness(llm), spans_by_example_id)
            )
        elif metric == "safety":
            if llm is None:
                raise ValueError("safety requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_safety(llm), spans_by_example_id)
            )
        elif metric == "trustworthiness":
            if llm is None:
                raise ValueError("trustworthiness requires an LLM; set --llm-provider and --llm-model")
            evaluators[metric] = create_evaluator(kind="LLM", name=metric)(
                _make_enriching_llm_evaluator(metric, make_trustworthiness(llm), spans_by_example_id)
            )
        else:
            raise ValueError(f"Unsupported metric: {metric}")
    return evaluators


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate terminal-bench experiment runs and write annotations back to A2E."
    )
    parser.add_argument("--base-url", default=os.getenv("A2E_BASE_URL", "http://localhost:6006"))
    parser.add_argument("--experiment-id", default=None)
    parser.add_argument("--dataset-name", default="terminal-bench-2")
    parser.add_argument("--experiment-name", default=None)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--metrics", default=",".join(TARGET_METRICS))
    parser.add_argument("--force", action="store_true", help="Re-run metrics even when annotations exist.")
    parser.add_argument("--dry-run", action="store_true", help="Compute but do not write annotations.")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--span-limit", type=int, default=1000)
    parser.add_argument("--llm-provider", default=os.getenv("A2E_EVAL_LLM_PROVIDER", "openai"))
    parser.add_argument("--llm-model", default=os.getenv("A2E_EVAL_LLM_MODEL", os.getenv("A2E_MODEL", "qwen-max")))
    parser.add_argument("--llm-base-url", default=os.getenv("OPENAI_API_BASE"))
    parser.add_argument("--llm-api-key", default=os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--llm-timeout", type=float, default=120.0)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(message)s")

    metric_names = [name.strip() for name in args.metrics.split(",") if name.strip()]
    unknown = sorted(set(metric_names) - set(TARGET_METRICS))
    if unknown:
        raise ValueError(f"Unsupported metric(s): {unknown}. Supported: {list(TARGET_METRICS)}")

    client = Client(base_url=args.base_url)
    experiment_id = args.experiment_id or _discover_experiment_id(
        client,
        dataset_name=args.dataset_name,
        experiment_name=args.experiment_name,
        timeout=args.timeout,
    )

    header = client.experiments.get(experiment_id=experiment_id)
    project_name = args.project_name or header.get("project_name")
    experiment = get_experiment(experiment_id=experiment_id, client=client)

    selected_metrics = _select_metrics(experiment, metric_names, force=args.force)
    if not selected_metrics:
        LOGGER.info("No metrics selected; all requested annotations already exist.")
        return

    spans_by_example_id = _fetch_spans_by_example_id(
        client,
        experiment,
        project_name=project_name,
        limit=args.span_limit,
        timeout=args.timeout,
    )
    llm = _create_llm(args) if any(metric in LLM_METRICS for metric in selected_metrics) else None
    evaluators = _build_evaluators(
        selected_metrics,
        llm=llm,
        spans_by_example_id=spans_by_example_id,
    )

    LOGGER.info(
        "evaluating experiment_id=%s project=%s metrics=%s dry_run=%s",
        experiment_id,
        project_name,
        ",".join(selected_metrics),
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

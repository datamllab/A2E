"""Backward-compatible entrypoint for terminal-bench evaluation.

The implementation is split across metric modules and `deal_server.py`:
- `core/agent_eval.py`: task_succeeded, error_absence, execution_completion
- `process_values/`: Plan, Skill, Memory, Tool, and Correct metrics
- `result_values/`: Safety and Efficiency metrics
- `result_values/safety_eval.py`: hallucination, faithfulness, refusal, evidence_consistency,
  privacy_leakage, unauthorized_action, harmful_action, overclaiming,
  uncertainty_calibration, failure_transparency, prompt_injection_resilience,
  tool_response_handling_safety, sandbox_escape_risk,
  tool_approval_compliance, evaluation_awareness, safety, trustworthiness
- `deal_server.py`: A2E server pull/evaluate/write-back orchestration
"""

from __future__ import annotations

import sys
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
if str(EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(EVAL_ROOT))

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
from core.deal_server import (
    LLM_METRICS,
    TARGET_METRICS,
    _build_evaluators,
    _completed_metric_names_by_run,
    _create_llm,
    _discover_experiment_id,
    _fetch_spans_by_example_id,
    _parse_datetime,
    _select_metrics,
    main,
    parse_args,
)
from core.eval_common import (
    _as_dict,
    _available_tools_str,
    _build_text_prompt,
    _dual_mode,
    _enrich_output,
    _final_answer,
    _first_expected,
    _initial_state_str,
    _json_dumps,
    _make_enriching_llm_evaluator,
    _numeric_attr,
    _score_to_dict,
    _span_attributes,
    _span_sort_key,
    _sum_cost,
    _sum_total_tokens,
    _task_output,
    _text_judge,
    _token_cost_spans,
    _tool_calls_from_spans,
    _tool_history_block,
)
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

__all__ = [
    "LLM_METRICS",
    "TARGET_METRICS",
    "_as_dict",
    "_available_tools_str",
    "_build_evaluators",
    "_build_text_prompt",
    "_completed_metric_names_by_run",
    "_create_llm",
    "_discover_experiment_id",
    "_dual_mode",
    "_enrich_output",
    "_fetch_spans_by_example_id",
    "_final_answer",
    "_first_expected",
    "_initial_state_str",
    "_json_dumps",
    "_make_enriching_llm_evaluator",
    "_numeric_attr",
    "_parse_datetime",
    "_score_to_dict",
    "_select_metrics",
    "_span_attributes",
    "_span_sort_key",
    "_sum_cost",
    "_sum_total_tokens",
    "_task_output",
    "_text_judge",
    "_token_cost_spans",
    "_tool_calls_from_spans",
    "_tool_history_block",
    "main",
    "make_conciseness",
    "make_correctness",
    "make_cost",
    "make_answer_cost",
    "make_error_absence",
    "make_evidence_consistency",
    "make_evaluation_awareness",
    "make_execution_completion",
    "make_faithfulness",
    "make_failure_transparency",
    "make_hallucination",
    "make_harmful_action",
    "make_instruction_following",
    "make_llm_judge",
    "make_overclaiming",
    "make_plan_completeness",
    "make_plan_constraint_adherence",
    "make_plan_goal_alignment",
    "make_plan_grade",
    "make_plan_hallucination",
    "make_privacy_leakage",
    "make_prompt_injection_resilience",
    "make_reasoning_coherence",
    "make_refusal",
    "make_safety",
    "make_sandbox_escape_risk",
    "make_self_correction_rate",
    "make_task_succeeded",
    "make_tool_approval_compliance",
    "make_tool_invocation",
    "make_tool_call_count",
    "make_tool_hallucination",
    "make_tool_recall",
    "make_tool_response_handling_safety",
    "make_tool_selection",
    "make_turn_count",
    "make_elapsed_time",
    "make_total_token_usage",
    "make_trustworthiness",
    "make_unauthorized_action",
    "make_uncertainty_calibration",
    "parse_args",
]


if __name__ == "__main__":
    main()

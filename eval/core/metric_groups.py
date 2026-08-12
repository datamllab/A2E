"""Metric groups used by the top-level evaluation runner."""

from __future__ import annotations

from collections.abc import Iterable

# Client-facing plan set: overall grade + four distinct failure modes.
# plan_correctness / reasoning_coherence remain in plan_eval.py (optional/manual).
PLAN_METRICS = (
    "plan_grade",
    "plan_goal_alignment",
    "plan_completeness",
    "plan_constraint_adherence",
    "plan_hallucination",
)

SKILL_METRICS = ("conciseness",)

# Answer faithfulness lives under safety as `hallucination` (not a separate memory group).
TOOL_METRICS = (
    "tool_hallucination",
    "tool_invocation",
    "tool_call_count",
    "self_correction_rate",
    "tool_recall",
)

CORRECT_METRICS = (
    "correctness",
    "task_succeeded",
)

EFFICIENCY_METRICS = (
    "total_token_usage",
    "cost",
    "turn_count",
    "elapsed_time",
)

SAFETY_METRICS = (
    "hallucination",
    "privacy_leakage",
    "unauthorized_action",
    "harmful_action",
    "failure_transparency",
    "prompt_injection_resilience",
)

METRIC_GROUPS = {
    "plan": PLAN_METRICS,
    "skill": SKILL_METRICS,
    "tool": TOOL_METRICS,
    "correct": CORRECT_METRICS,
    "efficiency": EFFICIENCY_METRICS,
    "safety": SAFETY_METRICS,
}

PART_ALIASES = {
    "all": "all",
    "plan": "plan",
    "plans": "plan",
    "skill": "skill",
    "skills": "skill",
    "memory": "safety",  # legacy alias: faithfulness lives under safety
    "mem": "safety",
    "tool": "tool",
    "tools": "tool",
    "correct": "correct",
    "correctness": "correct",
    "efficiency": "efficiency",
    "efficient": "efficiency",
    "safety": "safety",
    "safe": "safety",
    "safet": "safety",
}


def _dedupe(metrics: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for metric in metrics:
        if metric in seen:
            continue
        seen.add(metric)
        ordered.append(metric)
    return tuple(ordered)


def metrics_for_parts(parts: Iterable[str]) -> tuple[str, ...]:
    canonical_parts = [PART_ALIASES.get(part.strip().lower(), part.strip().lower()) for part in parts]
    if not canonical_parts or "all" in canonical_parts:
        return _dedupe(metric for group in METRIC_GROUPS.values() for metric in group)
    unknown = sorted({part for part in canonical_parts if part not in METRIC_GROUPS})
    if unknown:
        valid = ", ".join(["all", *METRIC_GROUPS])
        raise ValueError(f"Unsupported metric part(s): {unknown}. Supported parts: {valid}")
    return _dedupe(metric for part in canonical_parts for metric in METRIC_GROUPS[part])


ALL_METRICS = metrics_for_parts(("all",))

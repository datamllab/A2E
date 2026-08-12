"""One-call runners + registries that drive A2E experiments.

Public surface:
    - run_tau_claude / run_tau_langgraph   — convenience helpers for τ-bench
    - DATASETS / AGENTS / EVALUATORS        — name → factory registries
    - list_registries / make_llm_judge      — used by CLI + future UI form
"""

from ageneval.task.runners.registry import (
    AGENTS,
    DATASETS,
    EVALUATORS,
    build_experiment_metadata,
    framework_for_agent,
    list_registries,
    make_llm_judge,
)
from ageneval.task.runners.run_context import (
    DEFAULT_SAMPLE_SIZE,
    RunIdentity,
    SampleSelection,
    build_run_identity,
    new_run_id,
    sample_dataset,
)
from ageneval.task.runners.tau_claude_runner import run_tau_claude
from ageneval.task.runners.tau_langgraph_runner import run_tau_langgraph

__all__ = [
    "AGENTS",
    "DATASETS",
    "DEFAULT_SAMPLE_SIZE",
    "EVALUATORS",
    "RunIdentity",
    "SampleSelection",
    "build_experiment_metadata",
    "build_run_identity",
    "framework_for_agent",
    "list_registries",
    "make_llm_judge",
    "new_run_id",
    "run_tau_claude",
    "run_tau_langgraph",
    "sample_dataset",
]

"""SWE-bench dataset adapter for A2E (sandboxed code-fix evaluation).

Public API:
    load_swe_bench_tasks(variant, n, split) -> SWEBenchDataset
    build_swe_bench_binding()               -> AgentBinding (bash + editor tools)
    setup_swe_bench(task, sandbox)          -> SandboxScoringRunner setup hook
    score_swe_bench(task, sandbox, patch)   -> {"resolved": bool, ...}
"""

from ageneval.task.datasets.swe_bench.binding import build_swe_bench_binding
from ageneval.task.datasets.swe_bench.grader import score_swe_bench
from ageneval.task.datasets.swe_bench.loader import (
    SWEBenchDataset,
    load_swe_bench_tasks,
    setup_swe_bench,
)

__all__ = [
    "SWEBenchDataset",
    "build_swe_bench_binding",
    "load_swe_bench_tasks",
    "score_swe_bench",
    "setup_swe_bench",
]

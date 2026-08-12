"""SWE-bench Pro dataset adapter for A2E (sandboxed long-horizon code fixes).

SWE-bench Pro (ScaleAI) evaluates challenging, long-horizon software-engineering
tasks in professional OSS repos. Each instance runs in its official Docker Hub
image (``jefzda/sweap-images:{dockerhub_tag}``, repo at ``/app``); grading uses
the official per-instance ``run_script.sh`` + ``parser.py`` (vendored, MIT) and
the official resolved criterion: every fail_to_pass + pass_to_pass test PASSED.

Public API:
    load_swe_bench_pro_tasks(variant, n, split) -> SWEBenchProDataset
    build_swe_bench_pro_binding()               -> AgentBinding (bash + editor)
    setup_swe_bench_pro(task, sandbox)          -> SandboxScoringRunner setup hook
    score_swe_bench_pro(task, sandbox, patch)   -> {"resolved": bool, ...}
    grade_with_patch(instance, sandbox, patch)  -> grade an explicit patch (gold tests)
"""

from ageneval.task.datasets.swe_bench_pro.binding import build_swe_bench_pro_binding
from ageneval.task.datasets.swe_bench_pro.grader import (
    grade_with_patch,
    score_swe_bench_pro,
    setup_swe_bench_pro,
)
from ageneval.task.datasets.swe_bench_pro.loader import (
    SWEBenchProDataset,
    load_swe_bench_pro_tasks,
)

__all__ = [
    "SWEBenchProDataset",
    "build_swe_bench_pro_binding",
    "grade_with_patch",
    "load_swe_bench_pro_tasks",
    "score_swe_bench_pro",
    "setup_swe_bench_pro",
]

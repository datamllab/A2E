"""Terminal-Bench 2.0 dataset adapter for A2E."""

from ageneval.task.datasets.terminal_bench_2.binding import build_terminal_bench_2_binding
from ageneval.task.datasets.terminal_bench_2.grader import score_terminal_bench_2
from ageneval.task.datasets.terminal_bench_2.loader import (
    TerminalBench2Dataset,
    list_task_names,
    load_terminal_bench_2_tasks,
    setup_terminal_bench_2,
)

__all__ = [
    "TerminalBench2Dataset",
    "build_terminal_bench_2_binding",
    "list_task_names",
    "load_terminal_bench_2_tasks",
    "score_terminal_bench_2",
    "setup_terminal_bench_2",
]

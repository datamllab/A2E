"""τ-bench dataset adapter for A2E."""

from __future__ import annotations

from typing import Any

__all__ = [
    "TauBenchDataset",
    "build_tau_bench_binding",
    "get_tool_schemas",
    "load_tau_bench_tasks",
]


def __getattr__(name: str) -> Any:
    if name == "build_tau_bench_binding":
        from ageneval.task.datasets.tau_bench.binding import build_tau_bench_binding

        return build_tau_bench_binding
    if name in {"TauBenchDataset", "load_tau_bench_tasks"}:
        from ageneval.task.datasets.tau_bench.loader import TauBenchDataset, load_tau_bench_tasks

        return TauBenchDataset if name == "TauBenchDataset" else load_tau_bench_tasks
    if name == "get_tool_schemas":
        from ageneval.task.datasets.tau_bench.tools import get_tool_schemas

        return get_tool_schemas
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

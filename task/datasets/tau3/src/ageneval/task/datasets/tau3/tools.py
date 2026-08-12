"""τ³-bench tool schemas — retail/airline live schemas from τ-bench runtime."""

from __future__ import annotations

from typing import Any

from ageneval.task.datasets.tau_bench.runtime import get_tool_schemas as _tau_schemas


def get_tau3_tool_schemas(domain: str | None = "retail") -> list[dict[str, Any]]:
    resolved = "airline" if domain == "airline" else "retail"
    return _tau_schemas(resolved)

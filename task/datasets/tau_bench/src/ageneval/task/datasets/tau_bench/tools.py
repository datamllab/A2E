"""OpenAI-style tool schemas for τ-bench (v1), domain-specific.

Schemas come from the official Sierra ``Tool.get_info()`` implementations
(parameter names, types, required fields, descriptions). ``domain`` selects
retail vs airline — the union of both domains is *not* exposed, because mixing
airline reservation tools into a retail task is what produced 10+ useless calls.
"""

from __future__ import annotations

from typing import Any, Literal

from ageneval.task.datasets.tau_bench.runtime import get_tool_schemas as _get_tool_schemas

Domain = Literal["retail", "airline"]


def get_tool_schemas(domain: Domain | None = "retail") -> list[dict[str, Any]]:
    return _get_tool_schemas(domain or "retail")

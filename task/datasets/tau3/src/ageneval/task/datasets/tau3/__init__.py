"""τ³-bench (TEXT-only) dataset adapter for A2E.

Integrates the text tool-agent-user tasks of τ³-bench (sierra-research
tau2-bench @ dev/tau3). The benchmark's voice/audio modality is intentionally
excluded — see ``loader`` / ``README``.

Public API:
    load_tau3_tasks(n, split) -> Tau3Dataset
    build_tau3_binding()      -> AgentBinding (tool-calling)
    get_tau3_tool_schemas()   -> list[dict]
"""

from ageneval.task.datasets.tau3.binding import build_tau3_binding
from ageneval.task.datasets.tau3.loader import Tau3Dataset, load_tau3_tasks
from ageneval.task.datasets.tau3.tools import get_tau3_tool_schemas

__all__ = [
    "Tau3Dataset",
    "build_tau3_binding",
    "get_tau3_tool_schemas",
    "load_tau3_tasks",
]

"""Result dataclasses returned by ``AgentRunner.run``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

Status = Literal["ok", "error", "max_turns"]


@dataclass(frozen=True)
class ToolCall:
    """One tool invocation captured from an agent trajectory."""

    name: str
    arguments: Mapping[str, Any]
    result: Any = None
    error: str | None = None


@dataclass(frozen=True)
class TaskTrace:
    """Framework-agnostic trace of a single agent run on one ``TaskInput``.

    A ``trace_id`` is supplied when the run was wrapped in an OpenTelemetry
    span (which is normal for runs going through ``ExperimentRunner``); it
    enables joining offline evaluator scores back to the a2e-recorded
    trace tree.
    """

    task_id: str
    agent_name: str
    status: Status
    turns: int
    tool_calls: Sequence[ToolCall] = field(default_factory=tuple)
    final_answer: str | None = None
    elapsed_seconds: float = 0.0
    trace_id: str | None = None
    error: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)

"""Dataset abstractions for the A2E task layer.

A ``Dataset`` is any iterable producer of ``TaskInput`` records. Concrete
adapters (τ-bench, AgentBench, …) live in sibling workspace packages under
``task/datasets/*`` and implement the ``Dataset`` protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class TaskInput:
    """One example fed to an agent.

    Attributes:
        task_id: Stable identifier for the example (used in trace metadata).
        instruction: Natural-language user instruction the agent must follow.
        initial_state: Optional structured world / env state (e.g. a τ-bench
            retail database snapshot).
        expected_actions: Ground-truth tool calls the agent should make.
        expected_outputs: Ground-truth final text outputs / answers.
        metadata: Free-form metadata (split, domain, difficulty, …).
        sandbox: Optional sandbox spec for code-execution datasets (e.g.
            SWE-bench): a JSON-friendly ``{"type": "docker", "config":
            {"image": ..., "cwd": "/testbed"}}``. ``None`` for the common
            in-process (no-sandbox) datasets. Consumed by
            ``SandboxScoringRunner`` via ``ageneval.task.sandbox``.
    """

    task_id: str
    instruction: str
    initial_state: Mapping[str, Any] = field(default_factory=dict)
    expected_actions: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    expected_outputs: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    sandbox: Mapping[str, Any] | None = None


class Dataset(Protocol):
    """A dataset is any iterable of ``TaskInput`` with a name and length."""

    name: str

    def __iter__(self) -> Iterator[TaskInput]: ...

    def __len__(self) -> int: ...

"""Abstract base class for A2E agent runners.

Every agent implementation in ``task/agents/*`` subclasses ``AgentRunner`` and
implements ``run(task)`` as an ``async`` method that returns a ``TaskTrace``.

The instrumentation (monitor layer) is automatic — agents must NOT create
``OITracer`` or spans manually. Wrap the run inside ``ExperimentRunner`` so
the parent span is established and ``trace_id`` is captured.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ageneval.task.core.dataset import TaskInput
from ageneval.task.core.result import TaskTrace


class AgentRunner(ABC):
    """Run an agent over a single ``TaskInput`` and return a ``TaskTrace``.

    Subclasses must:
        1. Set ``self.name`` (used for span attributes and result tagging).
        2. Implement ``async def run(self, task) -> TaskTrace``.
    """

    name: str = "unnamed-agent"

    @abstractmethod
    async def run(self, task: TaskInput) -> TaskTrace:
        """Execute the agent on one task. Must be idempotent and side-effect-free
        outside of the OTel tracer it produces.
        """
        raise NotImplementedError

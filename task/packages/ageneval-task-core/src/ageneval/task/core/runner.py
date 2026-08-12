"""ExperimentRunner — orchestrate (dataset, agent, tracer) end-to-end.

Each task runs inside its own root span so a2e can group everything the
agent does under one trace.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import replace
from typing import Iterable

from opentelemetry import trace as trace_api
from opentelemetry.sdk.trace import TracerProvider

from ageneval.task.core.agent import AgentRunner
from ageneval.task.core.dataset import Dataset, TaskInput
from ageneval.task.core.instrumentation import shutdown
from ageneval.task.core.result import TaskTrace

logger = logging.getLogger(__name__)


class ExperimentRunner:
    """Run an agent over every task in a dataset and collect ``TaskTrace`` records.

    The runner is intentionally minimal: it owns the OTel root span for each
    task, captures ``trace_id``, handles per-task errors, and shuts the
    tracer down. Concrete agents do everything else.
    """

    def __init__(
        self,
        *,
        dataset: Dataset,
        agent: AgentRunner,
        tracer_provider: TracerProvider,
        concurrency: int = 1,
    ) -> None:
        self.dataset = dataset
        self.agent = agent
        self.tracer_provider = tracer_provider
        self.concurrency = max(1, concurrency)
        self._tracer = tracer_provider.get_tracer(__name__)

    async def run_all(self) -> list[TaskTrace]:
        """Run the agent over every task. Concurrency is capped by ``concurrency``."""
        tasks: Iterable[TaskInput] = list(self.dataset)
        sem = asyncio.Semaphore(self.concurrency)

        async def _one(task: TaskInput) -> TaskTrace:
            async with sem:
                return await self._run_one(task)

        return await asyncio.gather(*[_one(t) for t in tasks])

    async def _run_one(self, task: TaskInput) -> TaskTrace:
        start = time.perf_counter()
        span_name = f"experiment.task.{task.task_id}"
        with self._tracer.start_as_current_span(span_name) as span:
            span.set_attribute("a2e.task_id", task.task_id)
            span.set_attribute("a2e.dataset", self.dataset.name)
            span.set_attribute("a2e.agent", self.agent.name)
            trace_id = f"{span.get_span_context().trace_id:032x}"
            try:
                trace = await self.agent.run(task)
            except Exception as exc:  # noqa: BLE001
                logger.exception("agent crashed on %s", task.task_id)
                span.record_exception(exc)
                elapsed = time.perf_counter() - start
                return TaskTrace(
                    task_id=task.task_id,
                    agent_name=self.agent.name,
                    status="error",
                    turns=0,
                    elapsed_seconds=elapsed,
                    trace_id=trace_id,
                    error=str(exc),
                )
            # Backfill trace_id and elapsed if agent didn't set them.
            elapsed = trace.elapsed_seconds or (time.perf_counter() - start)
            return replace(trace, trace_id=trace.trace_id or trace_id, elapsed_seconds=elapsed)

    def close(self) -> None:
        shutdown(self.tracer_provider)

    def __enter__(self) -> "ExperimentRunner":
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()

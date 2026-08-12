"""One-shot runner for τ-bench × langgraph multi-agent."""

from __future__ import annotations

import asyncio
from typing import Literal, Sequence

from ageneval.task.core import (
    ExperimentRunner,
    TaskTrace,
    setup_instrumentation,
)
from ageneval.task.datasets.tau_bench import load_tau_bench_tasks

Domain = Literal["retail", "airline"]


def run_tau_langgraph(
    *,
    domain: Domain = "retail",
    n: int = 1,
    model: str | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    project_name: str | None = None,
    endpoint: str | None = None,
    concurrency: int = 1,
) -> Sequence[TaskTrace]:
    """Run ``n`` τ-bench tasks through the langgraph multi-agent graph."""
    from ageneval.task.agents.langgraph import LangGraphTauAgent

    provider = setup_instrumentation(
        project_name=project_name or f"tau-bench-langgraph-{domain}",
        endpoint=endpoint,
        framework="langchain",
    )
    dataset = load_tau_bench_tasks(domain=domain, n=n)
    agent = LangGraphTauAgent(
        domain=domain, model=model, api_base=api_base, api_key=api_key
    )

    with ExperimentRunner(
        dataset=dataset,
        agent=agent,
        tracer_provider=provider,
        concurrency=concurrency,
    ) as runner:
        traces = asyncio.run(runner.run_all())
    return tuple(traces)

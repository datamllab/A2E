"""One-shot runner for τ-bench × claude-agent-sdk."""

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


def run_tau_claude(
    *,
    domain: Domain = "retail",
    n: int = 1,
    model: str = "claude-sonnet-4-5",
    project_name: str | None = None,
    endpoint: str | None = None,
    concurrency: int = 1,
) -> Sequence[TaskTrace]:
    """Run ``n`` τ-bench tasks through the claude-agent-sdk single agent."""
    # Lazy import: optional dep.
    from ageneval.task.agents.claude_sdk import ClaudeSDKTauAgent

    provider = setup_instrumentation(
        project_name=project_name or f"tau-bench-claude-{domain}",
        endpoint=endpoint,
        framework="claude_agent_sdk",
    )
    dataset = load_tau_bench_tasks(domain=domain, n=n)
    agent = ClaudeSDKTauAgent(domain=domain, model=model)

    with ExperimentRunner(
        dataset=dataset,
        agent=agent,
        tracer_provider=provider,
        concurrency=concurrency,
    ) as runner:
        traces = asyncio.run(runner.run_all())
    return tuple(traces)

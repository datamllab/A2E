"""LangGraphAgent / LangGraphTauAgent — multi-agent runner.

Dataset-agnostic ``LangGraphAgent`` takes an ``AgentBinding`` and runs any
benchmark whose binding is provided. ``LangGraphTauAgent`` is a thin
backwards-compat wrapper that builds the τ-bench binding for the caller.
Auto-instrumented by ``LangChainInstrumentor``; each node additionally
wraps itself in an explicit ``AGENT`` span so the A2E UI separates the
three logical agents in a single trace.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from ageneval.task.core import AgentBinding, AgentRunner, TaskInput, TaskTrace, ToolCall

from ageneval.task.agents.langgraph.graph import build_tau_graph

logger = logging.getLogger(__name__)

# Unified model: default to .env's A2E_MODEL (a non-reasoning instruct model);
# fall back to qwen-plus. Never default to a model the configured endpoint
# does not serve.
_DEFAULT_MODEL = os.environ.get("A2E_MODEL") or "qwen-plus"


@dataclass
class LangGraphAgent(AgentRunner):
    """Generic multi-agent runner driven by a LangGraph state machine.

    Accepts any ``AgentBinding`` — adding a new benchmark means writing a
    new ``binding.py`` in ``task/datasets/<bench>/``; **no new agent file**.
    """

    binding: AgentBinding | None = None
    model: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    max_turns: int = 8

    name: str = field(init=False)

    def __post_init__(self) -> None:
        if self.binding is None:
            raise ValueError("LangGraphAgent requires a binding")
        self.name = f"langgraph-{self.binding.name}"
        self._model_name = (
            self.model
            or os.environ.get("A2E_LANGGRAPH_MODEL")
            or _DEFAULT_MODEL
        )

    async def run(self, task: TaskInput) -> TaskTrace:
        from langchain_openai import ChatOpenAI

        llm_kwargs: dict[str, Any] = {"model": self._model_name}
        if self.api_base or os.environ.get("OPENAI_API_BASE"):
            llm_kwargs["base_url"] = self.api_base or os.environ["OPENAI_API_BASE"]
        if self.api_key or os.environ.get("OPENAI_API_KEY"):
            llm_kwargs["api_key"] = self.api_key or os.environ["OPENAI_API_KEY"]
        llm = ChatOpenAI(**llm_kwargs)

        graph = build_tau_graph(llm=llm, binding=self.binding, max_turns=self.max_turns)

        start = time.perf_counter()
        try:
            final_state = await graph.ainvoke(
                {
                    "task": task,
                    "messages": [],
                    "tool_calls": [],
                    "final_answer": None,
                    "turns": 0,
                }
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start
            logger.exception("langgraph run failed on %s", task.task_id)
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="error",
                turns=0,
                elapsed_seconds=elapsed,
                error=str(exc),
            )
        elapsed = time.perf_counter() - start

        tool_calls = tuple(
            ToolCall(
                name=tc["name"],
                arguments=tc.get("arguments", {}),
                result=tc.get("result"),
            )
            for tc in final_state.get("tool_calls", [])
        )
        final_answer = final_state.get("final_answer")
        turns = int(final_state.get("turns", 0))
        status = (
            "ok"
            if final_answer is not None
            else ("max_turns" if turns >= self.max_turns else "error")
        )
        return TaskTrace(
            task_id=task.task_id,
            agent_name=self.name,
            status=status,
            turns=turns,
            tool_calls=tool_calls,
            final_answer=final_answer,
            elapsed_seconds=elapsed,
        )


# ─── backwards-compat wrapper for τ-bench ─────────────────────────────────────


@dataclass
class LangGraphTauAgent(LangGraphAgent):
    """Thin wrapper: ``LangGraphTauAgent(domain="retail")`` resolves the
    τ-bench binding automatically. New benchmarks should instead pass a
    custom ``AgentBinding`` directly to ``LangGraphAgent``.
    """

    domain: str = "retail"
    binding: AgentBinding | None = None  # auto-built from domain if None

    def __post_init__(self) -> None:  # type: ignore[override]
        if self.binding is None:
            # Late import so this package doesn't hard-depend on tau-bench at module load.
            from ageneval.task.datasets.tau_bench import build_tau_bench_binding

            self.binding = build_tau_bench_binding(self.domain)  # type: ignore[arg-type]
        super().__post_init__()

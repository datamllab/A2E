"""Build the multi-agent LangGraph.

Three nodes — ``router``, ``executor``, ``responder`` — each behaves as a
distinct logical agent and gets its own ``AGENT`` span in the trace.

The graph is **dataset-agnostic**: it consumes an ``AgentBinding`` for the
tool schemas + executor + system prompt, so the same graph drives any
benchmark that provides a binding.
"""

from __future__ import annotations

from typing import Any, TypedDict

from ageneval.task.core import AgentBinding, TaskInput, ToolCall

from ageneval.task.agents.langgraph.nodes import (
    executor_run,
    responder_node,
    router_node,
)


class TauGraphState(TypedDict, total=False):
    task: TaskInput
    messages: list[Any]
    tool_calls: list[dict[str, Any]]
    final_answer: str | None
    next_action: dict[str, Any] | None
    turns: int


def build_tau_graph(*, llm: Any, binding: AgentBinding, max_turns: int = 8) -> Any:
    """Compile the multi-agent graph for one (llm, binding, max_turns) trio."""
    from langgraph.graph import END, START, StateGraph

    def _router(state: TauGraphState) -> dict[str, Any]:
        return router_node(state=state, llm=llm, binding=binding)

    def _executor(state: TauGraphState) -> dict[str, Any]:
        return executor_run(state=state, binding=binding)

    def _responder(state: TauGraphState) -> dict[str, Any]:
        return responder_node(state=state, llm=llm)

    def _branch_after_router(state: TauGraphState) -> str:
        if state.get("final_answer") is not None:
            return "responder"
        if state.get("next_action"):
            if int(state.get("turns", 0)) >= max_turns:
                return "responder"
            return "executor"
        return "responder"

    graph = StateGraph(TauGraphState)
    graph.add_node("router", _router)
    graph.add_node("executor", _executor)
    graph.add_node("responder", _responder)
    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        _branch_after_router,
        {"executor": "executor", "responder": "responder"},
    )
    graph.add_edge("executor", "router")
    graph.add_edge("responder", END)
    return graph.compile()


__all__ = ["build_tau_graph", "TauGraphState", "ToolCall"]

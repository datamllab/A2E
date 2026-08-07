"""AgentBinding — the contract that lets a generic agent run on any dataset.

The dependency direction is::

    dataset package  ──provides──▶  AgentBinding  ──consumed by──▶  generic AgentRunner

Adding a new benchmark therefore costs **one** new file in
``task/datasets/<benchmark>/binding.py`` — no new agent file required.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence


class ToolExecutor(Protocol):
    """Execute a tool by name against the task's environment state.

    ``state`` is whatever the dataset put in ``TaskInput.initial_state``;
    the executor may mutate or return without side effects depending on the
    benchmark's semantics.
    """

    def __call__(self, name: str, arguments: Mapping[str, Any], state: Mapping[str, Any]) -> Any: ...


SystemPromptBuilder = Callable[[Sequence[Mapping[str, Any]]], str]
"""Build the system prompt given the active tool schemas."""


@dataclass(frozen=True)
class AgentBinding:
    """Everything a generic agent needs to handle a specific dataset.

    Attributes:
        name: Short identifier (used in span / experiment names), e.g. ``"tau-bench-retail"``.
        tool_schemas: OpenAI-style function specs for the tools the agent may invoke.
        tool_executor: Synchronous callable that runs a tool against ``TaskInput.initial_state``.
        system_prompt_builder: Returns the system prompt given ``tool_schemas``.
    """

    name: str
    tool_schemas: Sequence[Mapping[str, Any]]
    tool_executor: ToolExecutor
    system_prompt_builder: SystemPromptBuilder

    def render_system_prompt(self) -> str:
        return self.system_prompt_builder(self.tool_schemas)

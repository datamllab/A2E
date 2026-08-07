"""OpenAIAgentsAgent — single-agent runner powered by the OpenAI Agents SDK.

Dataset-agnostic: consumes an ``AgentBinding`` and drives any benchmark.
The ``openinference-instrumentation-openai-agents`` instrumentor (installed by
``setup_instrumentation(framework="openai_agents")``) captures spans
automatically. **Do not add manual spans inside this module.**

Module-level imports are restricted to core + stdlib: the ``agents`` / ``openai``
SDKs are imported lazily inside ``__post_init__`` and ``run`` so that
``import ageneval.task.agents.openai_agents`` never fails when the runtime SDK
is absent.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ageneval.task.core import AgentBinding, AgentRunner, TaskInput, TaskTrace, ToolCall

# Unified model: default to .env's A2E_MODEL (a non-reasoning instruct model);
# fall back to qwen-plus.
_DEFAULT_MODEL = os.environ.get("A2E_MODEL") or "qwen-plus"
_MAX_TURNS = 8


@dataclass(eq=False)
class OpenAIAgentsAgent(AgentRunner):
    """Single-agent runner powered by the OpenAI Agents SDK, framework-agnostic.

    Accepts any ``AgentBinding`` — adding a new benchmark means writing a new
    ``binding.py`` under ``task/datasets/<bench>/``; **no new agent file**. The
    OpenAI Agents SDK drives an LLM through an OpenAI-compatible endpoint; A2E's
    OpenInference instrumentor captures every step automatically.
    """

    binding: AgentBinding | None = None
    model: str = _DEFAULT_MODEL
    max_turns: int = _MAX_TURNS
    api_base: str | None = None
    api_key: str | None = None
    name: str = field(init=False)

    def __post_init__(self) -> None:
        if self.binding is None:
            raise ValueError("OpenAIAgentsAgent requires a binding")
        self.name = f"openai-agents-{self.binding.name}"
        try:
            import agents  # noqa: F401  — the openai-agents package
        except ImportError as exc:
            raise RuntimeError(
                "openai-agents agent requires its runtime SDK. Install with:\n"
                "  uv sync at the A2E workspace root"
            ) from exc

    async def run(self, task: TaskInput) -> TaskTrace:
        start = time.perf_counter()
        recorder: list[ToolCall] = []
        try:
            from agents import Agent, Runner, function_tool
            from agents.exceptions import MaxTurnsExceeded
            from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
            from openai import AsyncOpenAI

            api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
            api_base = self.api_base or os.environ.get("OPENAI_API_BASE")
            if not api_key:
                return TaskTrace(
                    task_id=task.task_id,
                    agent_name=self.name,
                    status="error",
                    turns=0,
                    tool_calls=(),
                    elapsed_seconds=time.perf_counter() - start,
                    error="openai-agents requires OPENAI_API_KEY",
                )
            client = AsyncOpenAI(api_key=api_key, base_url=api_base)

            assert self.binding is not None  # for type-checkers
            tools = _build_function_tools(self.binding, task, recorder, function_tool)
            agent = Agent(
                name=self.name,
                instructions=self.binding.render_system_prompt(),
                model=OpenAIChatCompletionsModel(model=self.model, openai_client=client),
                tools=tools,
            )
            result = await Runner.run(agent, task.instruction, max_turns=self.max_turns)
            final = str(getattr(result, "final_output", "") or "")
            turns = len(getattr(result, "raw_responses", []) or []) or len(recorder)
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="ok" if final else "error",
                turns=turns,
                tool_calls=tuple(recorder),
                final_answer=final or None,
                elapsed_seconds=time.perf_counter() - start,
            )
        except MaxTurnsExceeded:
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="max_turns",
                turns=self.max_turns,
                tool_calls=tuple(recorder),
                elapsed_seconds=time.perf_counter() - start,
            )
        except Exception as exc:
            # Broad catch: surface any SDK / network / parsing failure as an
            # error TaskTrace rather than crashing the whole experiment run.
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="error",
                turns=0,
                tool_calls=tuple(recorder),
                elapsed_seconds=time.perf_counter() - start,
                error=(str(exc) or type(exc).__name__)[:1000],
            )


def _build_function_tools(
    binding: AgentBinding,
    task: TaskInput,
    recorder: list[ToolCall],
    function_tool: Callable[..., Any],
) -> list[Any]:
    """Wrap each binding tool schema into an openai-agents function_tool.

    Each tool is a closure over the binding executor + the current task's
    ``initial_state`` + a shared ``recorder`` list so each invocation is also
    captured into ``TaskTrace.tool_calls``.
    """
    tools = []
    for schema in binding.tool_schemas:
        fn = schema["function"]
        name = fn["name"]

        def _make(tool_name: str, tool_description: str):
            @function_tool(
                name_override=tool_name,
                description_override=tool_description,
            )
            def _tool(arguments_json: str) -> str:
                """Invoke a benchmark tool. Pass a JSON object string of arguments."""
                args = json.loads(arguments_json or "{}")
                try:
                    result = binding.tool_executor(tool_name, args, task.initial_state)
                except Exception as exc:
                    # Broad catch: a failing tool must not abort the agent loop.
                    recorder.append(
                        ToolCall(name=tool_name, arguments=args, result=None, error=str(exc))
                    )
                    return json.dumps({"error": str(exc)}, default=str)
                recorder.append(ToolCall(name=tool_name, arguments=args, result=result))
                return json.dumps(result, default=str)

            return _tool

        tools.append(_make(name, fn.get("description", "")))
    return tools

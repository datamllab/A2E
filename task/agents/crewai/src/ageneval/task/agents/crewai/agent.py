"""CrewAIAgent — single-agent runner powered by the CrewAI framework.

Dataset-agnostic: consumes an ``AgentBinding`` and drives any benchmark.
The ``openinference-instrumentation-crewai`` instrumentor (installed by
``setup_instrumentation(framework="crewai")``) captures spans automatically.
**Do not add manual spans inside this module.**

Module-level imports are restricted to core + stdlib: the ``crewai`` SDK is
imported lazily inside ``__post_init__`` and ``run`` so that
``import ageneval.task.agents.crewai`` never fails when the runtime SDK is
absent.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from ageneval.task.core import AgentBinding, AgentRunner, TaskInput, TaskTrace, ToolCall

# Unified model: default to .env's A2E_MODEL (a non-reasoning instruct model);
# fall back to qwen-plus.
_DEFAULT_MODEL = os.environ.get("A2E_MODEL") or "qwen-plus"
_MAX_TURNS = 8


@dataclass(eq=False)
class CrewAIAgent(AgentRunner):
    """Single-agent runner powered by CrewAI, framework-agnostic.

    Accepts any ``AgentBinding`` — adding a new benchmark means writing a new
    ``binding.py`` under ``task/datasets/<bench>/``; **no new agent file**.
    CrewAI drives an LLM through an OpenAI-compatible endpoint (``crewai.LLM``
    with an ``openai/`` model prefix routed by litellm); A2E's OpenInference
    instrumentor captures every step automatically.
    """

    binding: AgentBinding | None = None
    model: str = _DEFAULT_MODEL
    max_turns: int = _MAX_TURNS
    api_base: str | None = None
    api_key: str | None = None
    name: str = field(init=False)

    def __post_init__(self) -> None:
        if self.binding is None:
            raise ValueError("CrewAIAgent requires a binding")
        self.name = f"crewai-{self.binding.name}"
        try:
            import crewai  # noqa: F401  — the crewai package
        except ImportError as exc:
            raise RuntimeError(
                "crewai agent requires its runtime SDK. Install with:\n"
                "  uv sync at the A2E workspace root"
            ) from exc

    async def run(self, task: TaskInput) -> TaskTrace:
        start = time.perf_counter()
        recorder: list[ToolCall] = []
        try:
            from crewai import LLM, Agent, Crew, Task

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
                    error="crewai requires OPENAI_API_KEY",
                )

            assert self.binding is not None  # for type-checkers
            # crewai routes through litellm; the ``openai/`` prefix selects the
            # OpenAI-compatible chat-completions provider so a non-official
            # model (e.g. qwen-plus) is driven via an OpenAI-style endpoint.
            llm = LLM(
                model=f"openai/{self.model}",
                base_url=api_base,
                api_key=api_key,
            )
            tools = _build_tools(self.binding, task, recorder)
            system_prompt = self.binding.render_system_prompt()
            agent = Agent(
                role="A2E benchmark agent",
                goal="Solve the user's task accurately using the available tools.",
                backstory=system_prompt,
                llm=llm,
                tools=tools,
                verbose=False,
                max_iter=self.max_turns,
            )
            crew_task = Task(
                description=task.instruction,
                expected_output="A concise, correct final answer to the task.",
                agent=agent,
            )
            crew = Crew(agents=[agent], tasks=[crew_task], verbose=False)

            # crewai's ``Crew.kickoff`` is synchronous; run it off the event
            # loop so the surrounding asyncio runner is not blocked.
            result = await asyncio.to_thread(crew.kickoff)

            final = _extract_final(result)
            turns = len(recorder) or (1 if final else 0)
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="ok" if final else "error",
                turns=turns,
                tool_calls=tuple(recorder),
                final_answer=final or None,
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


def _extract_final(result: Any) -> str:
    """Best-effort final-answer extraction from a crewai ``CrewOutput``."""
    if result is None:
        return ""
    raw = getattr(result, "raw", None)
    if raw:
        return str(raw).strip()
    return str(result).strip()


def _build_tools(
    binding: AgentBinding,
    task: TaskInput,
    recorder: list[ToolCall],
) -> list[Any]:
    """Wrap each binding tool schema into a crewai ``BaseTool`` instance.

    Each tool is a closure over the binding executor + the current task's
    ``initial_state`` + a shared ``recorder`` list so each invocation is also
    captured into ``TaskTrace.tool_calls``. crewai's ``BaseTool`` requires a
    pydantic ``args_schema``; a permissive single-field schema accepting a JSON
    object string keeps the wiring dataset-agnostic.
    """
    from pydantic import BaseModel, Field

    from crewai.tools import BaseTool

    class _ArgsSchema(BaseModel):
        arguments_json: str = Field(
            default="{}",
            description="A JSON object string of the tool arguments.",
        )

    tools: list[Any] = []
    for schema in binding.tool_schemas:
        fn = schema["function"]
        tool_name = fn["name"]
        tool_description = fn.get("description", "") or f"Invoke the {tool_name} tool."

        def _make(name: str, description: str) -> Any:
            bound_name = name
            bound_description = description

            def _invoke(arguments_json: str = "{}") -> str:
                try:
                    args = json.loads(arguments_json or "{}")
                except (ValueError, TypeError):
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                try:
                    result = binding.tool_executor(name, args, task.initial_state)
                except Exception as exc:
                    # A failing tool must not abort the agent loop.
                    recorder.append(
                        ToolCall(name=name, arguments=args, result=None, error=str(exc))
                    )
                    return json.dumps({"error": str(exc)}, default=str)
                recorder.append(ToolCall(name=name, arguments=args, result=result))
                return json.dumps(result, default=str)

            class _BindingTool(BaseTool):
                name: str = bound_name
                description: str = (
                    f"{bound_description}\n\n"
                    "Pass a JSON object string of arguments via 'arguments_json'."
                )
                args_schema: type = _ArgsSchema

                def _run(self, arguments_json: str = "{}") -> str:
                    return _invoke(arguments_json)

            return _BindingTool()

        tools.append(_make(tool_name, tool_description))
    return tools

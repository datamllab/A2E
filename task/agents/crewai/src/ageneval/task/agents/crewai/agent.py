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
from ageneval.task.core.budget import max_tokens as _max_tokens
from ageneval.task.core.budget import max_turns as _default_turns

_DEFAULT_MODEL = os.environ.get("A2E_MODEL") or "qwen-plus"
_MAX_TURNS = _default_turns()


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
                max_tokens=_max_tokens(),
            )
            tools = _build_tools(self.binding, task, recorder)
            if tools:
                # CrewAI 1.6 get_llm_response never forwards tools to
                # llm.call. The model then writes a ReAct Thought and
                # format_answer treats the parse failure as AgentFinish
                # (0 recorded tool calls). Bind native function-calling
                # schemas + executors onto every completion.
                _attach_native_tools(llm, tools, self.binding)
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
            tool_hint = ""
            if tools:
                names = ", ".join(getattr(t, "name", "tool") for t in tools)
                tool_hint = (
                    "You have tools and MUST use them via function calling "
                    f"before answering: {names}. Do not answer from memory "
                    "when a lookup tool exists.\n\n"
                )
            crew_task = Task(
                description=tool_hint + task.instruction,
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


def _attach_native_tools(llm: Any, tools: list[Any], binding: AgentBinding) -> None:
    """Inject OpenAI tool schemas into every ``llm.call``.

    CrewAI's ReAct loop asks the model for ``Action:`` text but does not
    put ``tools`` on the chat-completions request. Instruct models then
    emit a Thought and stop; 1.6's ``format_answer`` swallows the parse
    error as a final answer. Native function calling with
    ``tool_choice=required`` forces at least one named-arg tool call.
    """
    from ageneval.task.core.native_tools import openai_tool_dicts

    openai_tools = openai_tool_dicts(binding.tool_schemas)
    available = {t.name: t._run for t in tools}
    orig = llm.call
    n_calls = {"n": 0}

    def call(
        messages: Any,
        tools: Any = None,
        callbacks: Any = None,
        available_functions: Any = None,
        from_task: Any = None,
        from_agent: Any = None,
        response_model: Any = None,
    ) -> Any:
        n_calls["n"] += 1
        extra = dict(getattr(llm, "additional_params", None) or {})
        # First turn must call a tool; later turns may emit the final answer.
        extra["tool_choice"] = "required" if n_calls["n"] == 1 else "auto"
        llm.additional_params = extra
        return orig(
            messages,
            tools=tools or openai_tools,
            callbacks=callbacks,
            available_functions=available_functions or available,
            from_task=from_task,
            from_agent=from_agent,
            response_model=response_model,
        )

    llm.call = call


def _build_tools(
    binding: AgentBinding,
    task: TaskInput,
    recorder: list[ToolCall],
) -> list[Any]:
    """Wrap each binding tool schema into a crewai ``BaseTool`` instance.

    ``args_schema`` is generated from the dataset JSON Schema so the model
    sees real parameter names instead of a single ``arguments_json`` blob.
    """
    from crewai.tools import BaseTool

    from ageneval.task.core.native_tools import (
        invoke_binding_tool,
        openai_function,
        parameters_block,
        pydantic_args_model,
    )

    # Set name/description/args_schema via constructor kwargs, not class-body
    # defaults. Pydantic's model namespace treats `name`/`description` as the
    # fields being defined, so `name: str = tool_name` raises
    # ``NameError: name 'name' is not defined`` at class creation.
    class _BindingTool(BaseTool):
        def _run(self, **kwargs: Any) -> str:
            return invoke_binding_tool(
                tool_name=self.name,
                kwargs=kwargs,
                binding=binding,
                task=task,
                recorder=recorder,
            )

    tools: list[Any] = []
    for schema in binding.tool_schemas:
        fn = openai_function(schema)
        tool_name = str(fn.get("name") or "tool")
        tool_description = str(fn.get("description") or f"Invoke the {tool_name} tool.")
        args_model = pydantic_args_model(tool_name, parameters_block(schema))
        tools.append(
            _BindingTool(
                name=tool_name,
                description=tool_description,
                args_schema=args_model,
            )
        )
    return tools

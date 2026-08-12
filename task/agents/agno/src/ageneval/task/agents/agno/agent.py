"""AgnoAgent — single-agent runner powered by the Agno agent framework.

Dataset-agnostic: consumes an ``AgentBinding`` and drives any benchmark.
The ``openinference-instrumentation-agno`` instrumentor (installed by
``setup_instrumentation(framework="agno")``) captures spans automatically.
**Do not add manual spans inside this module.**

Module-level imports are restricted to core + stdlib: the ``agno`` SDK is
imported lazily inside ``__post_init__`` and ``run`` so that
``import ageneval.task.agents.agno`` never fails when the runtime SDK is
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
from ageneval.task.core.budget import llm_timeout as _llm_timeout
from ageneval.task.core.budget import max_tokens as _budget_tokens
from ageneval.task.core.budget import max_turns as _default_turns
from ageneval.task.core.budget import run_deadline as _run_deadline

_DEFAULT_MODEL = os.environ.get("A2E_MODEL") or "qwen-plus"
_MAX_TURNS = _default_turns()

# Per-request LLM timeout + retries. Without these a stalled connection to the
# OpenAI-compatible endpoint hangs the whole run forever (observed: a single
# qwen-max call stuck >20 min with the container idle). A bounded timeout makes
# a hung call fail fast and retry; a persistent failure raises and is recorded
# as an error trace (the task still gets a trajectory) so the run never stalls.
_LLM_TIMEOUT = _llm_timeout()
_LLM_MAX_RETRIES = int(os.environ.get("A2E_LLM_MAX_RETRIES", "2"))
# Reasoning models (e.g. kimi-k3) spend completion tokens on hidden
# reasoning_content before they emit a tool call. A low default cap makes
# finish_reason=length with empty content and zero tools.
_MAX_TOKENS = _budget_tokens()

# Whole-agent wall-clock deadline. agno's ``Agent.run`` is a *synchronous* call
# run via ``asyncio.to_thread``; a slow sandbox tool (e.g. compiling a C-extension
# library or running its test suite) can keep a single tool call busy for minutes,
# so a few of them exhaust any task budget. When this deadline fires we DON'T
# discard the work: the shared tool ``recorder`` already holds every call made so
# far, so we return a *partial* trajectory (status="timeout") instead of letting
# an outer ``asyncio.wait_for`` hard-cancel the thread and lose everything. Keep
# this BELOW the experiment runner's task cap so this branch wins and the
# trajectory (plus the sandbox diff/score) survives.
_RUN_DEADLINE = _run_deadline()

# Many dataset bindings prescribe a text JSON-action protocol ({"action": ...})
# that suits text-loop agents (e.g. langgraph). agno drives the model through
# NATIVE function-calling, so that instruction makes some models emit a JSON
# final answer in one turn without ever calling a tool (empty trajectory). This
# hint steers agno's model to actually invoke the provided functions.
_NATIVE_TOOL_HINT = (
    "\n\nIMPORTANT — how to act: the tools listed above are available to you as "
    "real callable functions. To take any action you MUST call the corresponding "
    "function directly with its arguments. Do NOT reply with an action as a JSON "
    "object in plain text — actually invoke the function. Explore and act via tool "
    "calls first; only write a plain-text final answer once you are done."
)


@dataclass(eq=False)
class AgnoAgent(AgentRunner):
    """Single-agent runner powered by the Agno framework, framework-agnostic.

    Accepts any ``AgentBinding`` — adding a new benchmark means writing a new
    ``binding.py`` under ``task/datasets/<bench>/``; **no new agent file**.
    Agno drives an LLM through an OpenAI-compatible endpoint (``OpenAILike``);
    A2E's OpenInference instrumentor captures every step automatically.
    """

    binding: AgentBinding | None = None
    model: str = _DEFAULT_MODEL
    max_turns: int = _MAX_TURNS
    api_base: str | None = None
    api_key: str | None = None
    request_timeout: float = _LLM_TIMEOUT
    max_retries: int = _LLM_MAX_RETRIES
    run_deadline: float = _RUN_DEADLINE
    name: str = field(init=False)

    def __post_init__(self) -> None:
        if self.binding is None:
            raise ValueError("AgnoAgent requires a binding")
        self.name = f"agno-{self.binding.name}"
        try:
            import agno  # noqa: F401  — the agno package
        except ImportError as exc:
            raise RuntimeError(
                "agno agent requires its runtime SDK. Install with:\n"
                "  uv sync at the A2E workspace root"
            ) from exc

    async def run(self, task: TaskInput) -> TaskTrace:
        start = time.perf_counter()
        recorder: list[ToolCall] = []
        try:
            from agno.agent import Agent
            from agno.models.openai.like import OpenAILike

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
                    error="agno requires OPENAI_API_KEY",
                )

            assert self.binding is not None  # for type-checkers
            model = OpenAILike(
                id=self.model,
                api_key=api_key,
                base_url=api_base,
                timeout=self.request_timeout,
                max_retries=self.max_retries,
                max_tokens=_MAX_TOKENS,
            )
            tools = _build_function_tools(self.binding, task, recorder)
            # Dataset overrides set max_turns (DeepSearchQA=20). Other harnesses
            # pass that budget into the SDK; without tool_call_limit agno loops
            # until A2E_AGNO_DEADLINE and returns an empty final_answer.
            agent = Agent(
                name="a2e_agent",
                model=model,
                tools=tools,
                instructions=self.binding.render_system_prompt() + _NATIVE_TOOL_HINT,
                tool_call_limit=self.max_turns,
            )

            # agno's ``Agent.run`` is synchronous; run it off the event loop so
            # the surrounding asyncio runner is not blocked (mirrors smolagents).
            # Bound it by a wall-clock deadline: a slow sandbox tool can block one
            # call for minutes. On timeout the worker thread keeps running (Python
            # threads can't be cancelled) but ``recorder`` already holds its work,
            # so we return a partial trajectory rather than losing it — the outer
            # SandboxScoringRunner still extracts the diff + score while the
            # container is alive, and tears the container down (killing the thread).
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(agent.run, task.instruction),
                    timeout=self.run_deadline,
                )
            except asyncio.TimeoutError:
                partial = tuple(recorder)
                return TaskTrace(
                    task_id=task.task_id,
                    agent_name=self.name,
                    status="timeout",
                    turns=len(partial),
                    tool_calls=partial,
                    final_answer=None,
                    elapsed_seconds=time.perf_counter() - start,
                    error=(
                        f"agent exceeded {self.run_deadline:.0f}s deadline "
                        f"after {len(partial)} tool call(s)"
                    ),
                )

            run_error = _run_error(result)
            if run_error is not None:
                return TaskTrace(
                    task_id=task.task_id,
                    agent_name=self.name,
                    status="error",
                    turns=_count_turns(result) or len(recorder),
                    tool_calls=tuple(recorder),
                    elapsed_seconds=time.perf_counter() - start,
                    error=run_error[:1000],
                )

            final = ""
            content = getattr(result, "content", None)
            if content is not None:
                final = str(content).strip()
            elif result is not None:
                final = str(result).strip()

            turns = _count_turns(result) or len(recorder)
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


def _count_turns(result: Any) -> int:
    """Best-effort turn count from an agno RunOutput object."""
    messages = getattr(result, "messages", None)
    if messages:
        return sum(1 for m in messages if getattr(m, "role", None) == "assistant")
    return 0


def _run_error(result: Any) -> str | None:
    """Return an SDK-reported terminal error instead of treating it as output."""
    status = getattr(result, "status", None)
    status_value = getattr(status, "value", status)
    normalized = str(status_value or "").upper()
    if normalized not in {"ERROR", "CANCELLED"}:
        return None
    content = getattr(result, "content", None)
    return str(content or f"Agno run ended with status {normalized}")


def _build_function_tools(
    binding: AgentBinding,
    task: TaskInput,
    recorder: list[ToolCall],
) -> list[Any]:
    """Wrap each binding tool schema into an agno ``Function`` with the tool's
    REAL parameter schema, so the model calls it natively.

    A binding's tools are dynamic (the JSON schema comes from the dataset), so
    we cannot write a static Python signature for them. Instead we construct
    ``agno.tools.function.Function`` directly, handing agno the OpenAI-format
    ``parameters`` schema verbatim and setting ``skip_entrypoint_processing=True``
    so agno uses that schema AS-IS: no signature reflection, no pydantic
    ``validate_call`` wrapping of our closure.

    This is what makes the model emit ``bash(command="...")`` natively rather
    than guessing a generic ``arguments_json`` blob or nesting everything under
    a spurious ``kwargs`` object (which silently dropped the real arguments and
    produced empty sandbox trajectories). agno invokes the entrypoint as
    ``entrypoint(**model_arguments)``, so the tool's arguments arrive directly
    as keyword args. Each invocation is captured into ``TaskTrace.tool_calls``.
    """
    from agno.tools.function import Function

    tools: list[Any] = []
    for schema in binding.tool_schemas:
        fn = schema["function"]
        name = fn["name"]
        description = fn.get("description", "") or f"Invoke the {name} tool."
        parameters = dict(fn.get("parameters") or {"type": "object", "properties": {}})

        def _make(tool_name: str):
            def _tool(**kwargs: Any) -> str:
                from ageneval.task.core.native_tools import invoke_binding_tool

                return invoke_binding_tool(
                    tool_name=tool_name,
                    kwargs=kwargs,
                    binding=binding,
                    task=task,
                    recorder=recorder,
                )

            return _tool

        tools.append(
            Function(
                name=name,
                description=description,
                parameters=parameters,
                entrypoint=_make(name),
                skip_entrypoint_processing=True,
            )
        )
    return tools

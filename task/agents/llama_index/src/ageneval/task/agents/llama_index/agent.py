"""LlamaIndexAgent — single-agent runner powered by LlamaIndex.

Dataset-agnostic: consumes an ``AgentBinding`` and drives any benchmark.
The ``openinference-instrumentation-llama-index`` instrumentor (installed by
``setup_instrumentation(framework="llama_index")``) captures spans
automatically. **Do not add manual spans inside this module.**

Module-level imports are restricted to core + stdlib: the ``llama_index`` /
``openai`` SDKs are imported lazily inside ``__post_init__`` and ``run`` so that
``import ageneval.task.agents.llama_index`` never fails when the runtime SDK is
absent.
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
class LlamaIndexAgent(AgentRunner):
    """Single-agent runner powered by LlamaIndex, framework-agnostic.

    Accepts any ``AgentBinding`` — adding a new benchmark means writing a new
    ``binding.py`` under ``task/datasets/<bench>/``; **no new agent file**.
    LlamaIndex's ``FunctionAgent`` drives an LLM through an OpenAI-compatible
    endpoint (``OpenAILike``); A2E's OpenInference instrumentor captures every
    step automatically.
    """

    binding: AgentBinding | None = None
    model: str = _DEFAULT_MODEL
    max_turns: int = _MAX_TURNS
    api_base: str | None = None
    api_key: str | None = None
    name: str = field(init=False)

    def __post_init__(self) -> None:
        if self.binding is None:
            raise ValueError("LlamaIndexAgent requires a binding")
        self.name = f"llama-index-{self.binding.name}"
        try:
            import llama_index.core  # noqa: F401  — the llama-index-core package
        except ImportError as exc:
            raise RuntimeError(
                "llama-index agent requires its runtime SDK. Install with:\n"
                "  uv sync at the A2E workspace root"
            ) from exc

    async def run(self, task: TaskInput) -> TaskTrace:
        start = time.perf_counter()
        recorder: list[ToolCall] = []
        try:
            from llama_index.core.agent.workflow import FunctionAgent
            from llama_index.core.tools import FunctionTool
            from llama_index.llms.openai_like import OpenAILike

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
                    error="llama-index requires OPENAI_API_KEY",
                )

            assert self.binding is not None  # for type-checkers
            llm = OpenAILike(
                model=self.model,
                api_base=api_base,
                api_key=api_key,
                is_chat_model=True,
                is_function_calling_model=True,
                temperature=1.0,
            )
            tools = _build_function_tools(self.binding, task, recorder, FunctionTool)
            agent = FunctionAgent(
                tools=tools,
                llm=llm,
                system_prompt=self.binding.render_system_prompt(),
            )
            result = await agent.run(
                task.instruction,
                max_iterations=self.max_turns,
            )
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
            error = (str(exc) or type(exc).__name__)[:1000]
            reached_limit = "Max iterations of" in error
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="max_turns" if reached_limit else "error",
                turns=self.max_turns if reached_limit else len(recorder),
                tool_calls=tuple(recorder),
                elapsed_seconds=time.perf_counter() - start,
                error=error,
            )


def _extract_final(result: Any) -> str:
    """Best-effort final-answer extraction from a FunctionAgent run result.

    ``FunctionAgent.run`` returns an ``AgentOutput`` (newer LlamaIndex) whose
    ``.response`` is a ``ChatMessage``; older versions may return a plain
    string. Cover both.
    """
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    response = getattr(result, "response", None)
    if response is None:
        return str(result).strip()
    if isinstance(response, str):
        return response.strip()
    # ChatMessage: prefer .content, fall back to str().
    content = getattr(response, "content", None)
    if content:
        return str(content).strip()
    return str(response).strip()


def _build_function_tools(
    binding: AgentBinding,
    task: TaskInput,
    recorder: list[ToolCall],
    function_tool_cls: Callable[..., Any],
) -> list[Any]:
    """Wrap each binding tool schema into a LlamaIndex ``FunctionTool``.

    Each tool is a closure over the binding executor + the current task's
    ``initial_state`` + a shared ``recorder`` list so each invocation is also
    captured into ``TaskTrace.tool_calls``.
    """
    tools: list[Any] = []
    for schema in binding.tool_schemas:
        fn = schema["function"]
        name = fn["name"]
        description = fn.get("description", "") or f"Invoke the {name} tool."

        def _make(tool_name: str, tool_description: str):
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

            return function_tool_cls.from_defaults(
                fn=_tool,
                name=tool_name,
                description=(
                    f"{tool_description} Pass a single argument `arguments_json`: "
                    "a JSON object string of the tool arguments."
                ),
            )

        tools.append(_make(name, description))
    return tools

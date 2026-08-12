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
from ageneval.task.core.budget import max_tokens as _max_tokens
from ageneval.task.core.budget import max_turns as _default_turns

_DEFAULT_MODEL = os.environ.get("A2E_MODEL") or "qwen-plus"
_MAX_TURNS = _default_turns()


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
                max_tokens=_max_tokens(),
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


def _usable_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"assistant:", "assistant", "none"}:
        return ""
    return text


def _extract_final(result: Any) -> str:
    """Best-effort final-answer extraction from a FunctionAgent run result.

    ``FunctionAgent.run`` returns an ``AgentOutput`` (newer LlamaIndex) whose
    ``.response`` is a ``ChatMessage``; older versions may return a plain
    string. kimi-k3 sometimes leaves ``content`` empty and puts text in
    ``additional_kwargs`` / blocks; ``str(ChatMessage)`` is then just
    ``assistant:``.
    """
    if result is None:
        return ""
    if isinstance(result, str):
        return _usable_text(result)
    response = getattr(result, "response", None)
    if response is None:
        return _usable_text(result)
    if isinstance(response, str):
        return _usable_text(response)
    content = _usable_text(getattr(response, "content", None))
    if content:
        return content
    for block in getattr(response, "blocks", None) or ():
        text = _usable_text(getattr(block, "text", None) or getattr(block, "content", None))
        if text:
            return text
    extra = getattr(response, "additional_kwargs", None) or {}
    if isinstance(extra, dict):
        for key in ("reasoning_content", "text", "output_text"):
            text = _usable_text(extra.get(key))
            if text:
                return text
    return _usable_text(response)


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
    from ageneval.task.core.native_tools import make_kwargs_tool

    tools: list[Any] = []
    for schema in binding.tool_schemas:
        native = make_kwargs_tool(
            schema=schema, binding=binding, task=task, recorder=recorder
        )
        tools.append(
            function_tool_cls.from_defaults(
                fn=native,
                name=native.__name__,
                description=(native.__doc__ or "").split("\n\nArgs:")[0],
            )
        )
    return tools

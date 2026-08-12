"""AutogenAgentChatAgent — single-agent runner powered by Microsoft AutoGen.

Dataset-agnostic: consumes an ``AgentBinding`` and drives any benchmark.
The ``openinference-instrumentation-autogen-agentchat`` instrumentor (installed
by ``setup_instrumentation(framework="autogen_agentchat")``) captures spans
automatically. **Do not add manual spans inside this module.**

Module-level imports are restricted to core + stdlib: the ``autogen_agentchat``
/ ``autogen_ext`` / ``autogen_core`` SDKs are imported lazily inside
``__post_init__`` and ``run`` so that ``import
ageneval.task.agents.autogen_agentchat`` never fails when the runtime SDK is
absent.

ISOLATION NOTE: AutoGen lives in an isolated uv project (see this package's
README.md) because ``autogen-core`` pins ``protobuf<5.30`` while A2E needs
``protobuf>=6.31``. The two cannot share one environment.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from ageneval.task.core import AgentBinding, AgentRunner, TaskInput, TaskTrace, ToolCall

# Unified model: default to .env's A2E_MODEL (a non-reasoning instruct model);
# fall back to qwen-plus.
from ageneval.task.core.budget import llm_timeout as _llm_timeout
from ageneval.task.core.budget import max_tokens as _max_tokens
from ageneval.task.core.budget import max_turns as _default_turns

_DEFAULT_MODEL = os.environ.get("A2E_MODEL") or "qwen-plus"
_MAX_TURNS = _default_turns()


@dataclass(eq=False)
class AutogenAgentChatAgent(AgentRunner):
    """Single-agent runner powered by AutoGen AgentChat, framework-agnostic.

    Accepts any ``AgentBinding`` — adding a new benchmark means writing a new
    ``binding.py`` under ``task/datasets/<bench>/``; **no new agent file**.
    AutoGen drives an LLM through an OpenAI-compatible endpoint
    (``OpenAIChatCompletionClient``); A2E's OpenInference instrumentor captures
    every step automatically.
    """

    binding: AgentBinding | None = None
    model: str = _DEFAULT_MODEL
    max_turns: int = _MAX_TURNS
    api_base: str | None = None
    api_key: str | None = None
    name: str = field(init=False)

    def __post_init__(self) -> None:
        if self.binding is None:
            raise ValueError("AutogenAgentChatAgent requires a binding")
        self.name = f"autogen-agentchat-{self.binding.name}"
        try:
            import autogen_agentchat  # noqa: F401  — the autogen-agentchat package
        except ImportError as exc:
            raise RuntimeError(
                "autogen-agentchat agent requires its runtime SDK. Because "
                "autogen-core conflicts with A2E on protobuf, this agent "
                "lives in an isolated uv project. Install with:\n"
                "  cd task/agents/autogen_agentchat && "
                "uv sync --index-strategy unsafe-best-match"
            ) from exc

    async def run(self, task: TaskInput) -> TaskTrace:
        start = time.perf_counter()
        recorder: list[ToolCall] = []
        try:
            from autogen_agentchat.agents import AssistantAgent
            from autogen_ext.models.openai import OpenAIChatCompletionClient

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
                    error="autogen-agentchat requires OPENAI_API_KEY",
                )

            assert self.binding is not None  # for type-checkers
            # Unified budget: timeout always; max_tokens if this SDK accepts it.
            client_kwargs: dict[str, Any] = {
                "model": self.model,
                "base_url": api_base,
                "api_key": api_key,
                "model_info": _build_model_info(self.model),
                "timeout": _llm_timeout(),
            }
            try:
                model_client = OpenAIChatCompletionClient(
                    **client_kwargs,
                    max_tokens=_max_tokens(),
                )
            except TypeError:
                model_client = OpenAIChatCompletionClient(**client_kwargs)
            tools = _build_function_tools(self.binding, task, recorder)
            agent = AssistantAgent(
                name="a2e_agent",
                model_client=model_client,
                tools=tools,
                system_message=self.binding.render_system_prompt(),
                max_tool_iterations=self.max_turns,
            )
            result = await agent.run(task=task.instruction)
            try:
                await model_client.close()
            except Exception:  # noqa: BLE001 — best-effort cleanup
                pass

            final = _extract_final(result)
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


def _build_model_info(model: str) -> dict[str, Any]:
    """Build a ``ModelInfo`` dict for a non-OpenAI-official model.

    ``OpenAIChatCompletionClient`` cannot infer capabilities for models it does
    not recognise (e.g. ``qwen-plus``), so an explicit ``model_info`` is
    required. Keys mirror the ``autogen_core.models.ModelInfo`` TypedDict;
    ``structured_output`` and ``multiple_system_messages`` are recent additions
    that older autogen-core versions tolerate as extra keys.
    """
    return {
        "vision": False,
        "function_calling": True,
        "json_output": True,
        "family": "unknown",
        "structured_output": True,
        "multiple_system_messages": True,
    }


def _extract_final(result: Any) -> str:
    """Best-effort final-answer extraction from an autogen ``TaskResult``."""
    messages = getattr(result, "messages", None) or []
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if content is None:
            continue
        if isinstance(content, str):
            text = content.strip()
            if text:
                return text
        elif isinstance(content, list):
            parts = [str(p) for p in content if isinstance(p, str)]
            text = " ".join(parts).strip()
            if text:
                return text
    return ""


def _count_turns(result: Any) -> int:
    """Best-effort turn count: number of model-produced text messages."""
    messages = getattr(result, "messages", None) or []
    return sum(1 for m in messages if type(m).__name__ == "TextMessage")


def _build_function_tools(
    binding: AgentBinding,
    task: TaskInput,
    recorder: list[ToolCall],
) -> list[Any]:
    """Wrap each binding tool schema into a plain Python function for AutoGen.

    AutoGen infers the published schema from the function signature. We attach
    the dataset JSON-Schema properties as keyword-only parameters.
    """
    from ageneval.task.core.native_tools import make_kwargs_tool

    return [
        make_kwargs_tool(schema=schema, binding=binding, task=task, recorder=recorder)
        for schema in binding.tool_schemas
    ]

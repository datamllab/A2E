"""GoogleADKAgent — single-agent runner powered by the Google Agent Development Kit.

Dataset-agnostic: consumes an ``AgentBinding`` and drives any benchmark.
The ``openinference-instrumentation-google-adk`` instrumentor (installed by
``setup_instrumentation(framework="google_adk")``) captures spans
automatically. **Do not add manual spans inside this module.**

Module-level imports are restricted to core + stdlib: the ``google.adk`` /
``litellm`` SDKs are imported lazily inside ``__post_init__`` and ``run`` so
that ``import ageneval.task.agents.google_adk`` never fails when the runtime
SDK is absent.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ageneval.task.core import AgentBinding, AgentRunner, TaskInput, TaskTrace, ToolCall

# Unified model: default to .env's A2E_MODEL (a non-reasoning instruct model);
# fall back to qwen-plus.
from ageneval.task.core.budget import max_tokens as _max_tokens
from ageneval.task.core.budget import max_turns as _default_turns

_DEFAULT_MODEL = os.environ.get("A2E_MODEL") or "qwen-plus"
_MAX_TURNS = _default_turns()
_APP_NAME = "a2e-google-adk"


@dataclass(eq=False)
class GoogleADKAgent(AgentRunner):
    """Single-agent runner powered by the Google ADK, framework-agnostic.

    Accepts any ``AgentBinding`` — adding a new benchmark means writing a new
    ``binding.py`` under ``task/datasets/<bench>/``; **no new agent file**. The
    Google ADK drives an LLM through an OpenAI-compatible endpoint (via
    LiteLLM); A2E's OpenInference instrumentor captures every step
    automatically.
    """

    binding: AgentBinding | None = None
    model: str = _DEFAULT_MODEL
    max_turns: int = _MAX_TURNS
    api_base: str | None = None
    api_key: str | None = None
    name: str = field(init=False)

    def __post_init__(self) -> None:
        if self.binding is None:
            raise ValueError("GoogleADKAgent requires a binding")
        self.name = f"google-adk-{self.binding.name}"
        try:
            import google.adk  # noqa: F401  — the google-adk package
        except ImportError as exc:
            raise RuntimeError(
                "google-adk agent requires its runtime SDK. Install with:\n"
                "  uv sync at the A2E workspace root"
            ) from exc

    async def run(self, task: TaskInput) -> TaskTrace:
        start = time.perf_counter()
        recorder: list[ToolCall] = []
        try:
            from google.adk.agents import Agent
            from google.adk.models.lite_llm import LiteLlm
            from google.adk.runners import InMemoryRunner
            from google.genai import types as genai_types

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
                    error="google-adk requires OPENAI_API_KEY",
                )

            # ADK's LiteLlm routes LLM calls through ``litellm.acompletion``.
            # litellm's default aiohttp async transport is rejected (HTTP 502)
            # by some OpenAI-compatible proxies; force litellm's async path
            # onto its httpx transport, which those proxies accept.
            os.environ.setdefault("DISABLE_AIOHTTP_TRANSPORT", "True")

            assert self.binding is not None  # for type-checkers
            llm = LiteLlm(
                model=f"openai/{self.model}",
                api_base=api_base,
                api_key=api_key,
                max_tokens=_max_tokens(),
            )
            tools = _build_function_tools(self.binding, task, recorder)
            agent = Agent(
                name="a2e_agent",
                model=llm,
                instruction=self.binding.render_system_prompt(),
                tools=tools,
            )
            runner = InMemoryRunner(agent=agent, app_name=_APP_NAME)

            user_id = "a2e-user"
            session_id = uuid.uuid4().hex
            await runner.session_service.create_session(
                app_name=_APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )
            user_text = task.instruction
            if tools:
                names = ", ".join(
                    getattr(getattr(t, "func", None), "__name__", None)
                    or getattr(t, "name", "tool")
                    for t in tools
                )
                user_text = (
                    "You have tools and MUST call them via function calling "
                    f"before answering: {names}. Do not answer from memory "
                    "when a lookup tool exists.\n\n"
                    + task.instruction
                )
            message = genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=user_text)],
            )

            final = ""
            llm_turns = 0
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=message,
            ):
                if getattr(event, "content", None) is not None:
                    author = getattr(event, "author", None)
                    if author and author != "user":
                        llm_turns += 1
                    text = _extract_text(event)
                    if text and event.is_final_response():
                        final = text
                    elif text:
                        # keep last model text as a fallback final answer
                        final = final or text
                if llm_turns >= self.max_turns + 1:
                    break

            turns = llm_turns or len(recorder)
            status = "ok" if final else "error"
            if not final and turns > self.max_turns:
                status = "max_turns"
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status=status,
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


def _extract_text(event: Any) -> str:
    """Concatenate text parts from an ADK event's content."""
    content = getattr(event, "content", None)
    if content is None:
        return ""
    parts = getattr(content, "parts", None) or []
    texts = [str(getattr(p, "text", "") or "") for p in parts]
    return "".join(t for t in texts if t).strip()


def _build_function_tools(
    binding: AgentBinding,
    task: TaskInput,
    recorder: list[ToolCall],
) -> list[Any]:
    """Wrap each binding tool schema into a google-adk FunctionTool.

    google-adk builds the model-facing schema from the Python signature.
    We attach the dataset JSON-Schema properties as keyword-only parameters
    so the model sees real fields (not a single ``arguments_json`` blob).
    """
    from google.adk.tools import FunctionTool

    from ageneval.task.core.native_tools import make_kwargs_tool

    tools: list[Any] = []
    for schema in binding.tool_schemas:
        tools.append(
            FunctionTool(
                func=make_kwargs_tool(
                    schema=schema, binding=binding, task=task, recorder=recorder
                )
            )
        )
    return tools

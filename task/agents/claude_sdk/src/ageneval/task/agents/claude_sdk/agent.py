"""ClaudeSDKAgent / ClaudeSDKTauAgent — single-agent runner (Anthropic SDK).

Dataset-agnostic ``ClaudeSDKAgent`` takes an ``AgentBinding`` and drives any
benchmark whose binding is provided. It uses the official Anthropic Python
SDK (``anthropic`` package) over the Messages API with **native tool use** —
no ``claude`` CLI subprocess. Point it at any Anthropic-compatible endpoint
(including OpenAI-style gateways that also expose ``/v1/messages``) via the
``ANTHROPIC_BASE_URL`` / ``ANTHROPIC_API_KEY`` environment variables.

``ClaudeSDKTauAgent`` is a thin backwards-compat wrapper that builds the
τ-bench binding for the caller.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ageneval.task.core import AgentBinding, AgentRunner, TaskInput, TaskTrace, ToolCall

logger = logging.getLogger(__name__)

from ageneval.task.core.budget import llm_timeout as _llm_timeout
from ageneval.task.core.budget import max_tokens as _budget_tokens
from ageneval.task.core.budget import max_turns as _default_turns

_MAX_TURNS = _default_turns()
_MAX_TOKENS = _budget_tokens()
# Unified model: default to .env's A2E_MODEL (a non-reasoning instruct model);
# fall back to qwen-plus. The endpoint gateway maps the model name.
_DEFAULT_MODEL = os.environ.get("A2E_MODEL") or "qwen-plus"

# Matches a (possibly nested one level) JSON object embedded in free text —
# used for the JSON-action protocol some dataset bindings prescribe in their
# system prompt (e.g. τ-bench: ``{"action": ..., "arguments": ...}``).
_JSON_RE = re.compile(r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}", re.DOTALL)


def _parse_json(text: str) -> dict[str, Any]:
    """Best-effort: extract the first JSON object from ``text``."""
    match = _JSON_RE.search(text or "")
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _to_anthropic_tools(schemas: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI-style function specs into Anthropic tool schema.

    OpenAI: ``{"type":"function","function":{"name","description","parameters"}}``
    Anthropic: ``{"name","description","input_schema"}``.
    """
    tools: list[dict[str, Any]] = []
    for schema in schemas:
        fn = schema.get("function", schema)
        name = str(fn.get("name", "tool"))
        params = fn.get("parameters") or {"type": "object", "properties": {}}
        tools.append(
            {
                "name": name,
                "description": str(fn.get("description", "") or name),
                "input_schema": dict(params),
            }
        )
    return tools


def _blocks_to_dicts(content: Any) -> list[dict[str, Any]]:
    """Serialise a response's content blocks to plain dicts for the next turn."""
    out: list[dict[str, Any]] = []
    for block in content or []:
        if hasattr(block, "model_dump"):
            out.append(block.model_dump())
        elif isinstance(block, dict):
            out.append(block)
    return out


def _text_of(content: Any) -> str:
    """Join visible and thinking text from an assistant message.

    kimi-k3 on the Anthropic Messages gateway often returns only
    ``thinking`` / ``reasoning_content`` blocks and an empty ``text``
    block. Treating that as no answer made gdpval-aa look like a
    harness failure.
    """
    parts: list[str] = []
    for block in content or []:
        btype = getattr(block, "type", None)
        if btype is None and isinstance(block, dict):
            btype = block.get("type")
            text = (
                block.get("text")
                or block.get("thinking")
                or block.get("reasoning_content")
                or ""
            )
        else:
            text = (
                getattr(block, "text", None)
                or getattr(block, "thinking", None)
                or getattr(block, "reasoning_content", None)
                or ""
            )
        if btype in {"text", "thinking", "reasoning"} or text:
            if text:
                parts.append(str(text))
    return "\n".join(p for p in parts if p).strip()


@dataclass
class ClaudeSDKAgent(AgentRunner):
    """Single-agent runner powered by the Anthropic Python SDK.

    Accepts any ``AgentBinding`` — adding a new benchmark means writing a new
    ``binding.py`` under ``task/datasets/<bench>/``; **no new agent file**.
    Talks to the Anthropic Messages API directly (no subprocess); set
    ``ANTHROPIC_BASE_URL`` to route through an Anthropic-compatible gateway.
    """

    binding: AgentBinding | None = None
    model: str = _DEFAULT_MODEL
    max_turns: int = _MAX_TURNS
    api_base: str | None = None
    api_key: str | None = None

    name: str = field(init=False)

    def __post_init__(self) -> None:
        if self.binding is None:
            raise ValueError("ClaudeSDKAgent requires a binding")
        self.name = f"claude-sdk-{self.binding.name}"

    async def run(self, task: TaskInput) -> TaskTrace:
        # Lazy import: the SDK is an optional runtime dependency.
        from anthropic import AsyncAnthropic  # type: ignore

        start = time.perf_counter()
        api_key = (
            self.api_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
        base_url = (
            self.api_base
            or os.environ.get("ANTHROPIC_BASE_URL")
            or os.environ.get("OPENAI_API_BASE")
        )
        # Anthropic SDK posts to ``{base_url}/v1/messages``. OpenAI-compatible
        # gateways usually set OPENAI_API_BASE to ``.../v1``; strip that suffix
        # so we do not request ``/v1/v1/messages``.
        if base_url:
            stripped = base_url.rstrip("/")
            if stripped.endswith("/v1"):
                base_url = stripped[: -len("/v1")] or stripped

        if not api_key:
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="error",
                turns=0,
                elapsed_seconds=time.perf_counter() - start,
                error=(
                    "ClaudeSDKAgent requires ANTHROPIC_API_KEY or OPENAI_API_KEY. "
                    "Set ANTHROPIC_BASE_URL (or OPENAI_API_BASE) for a gateway."
                ),
            )

        assert self.binding is not None  # for type-checkers
        timeout = _llm_timeout()
        client = AsyncAnthropic(
            api_key=api_key, base_url=base_url or None, timeout=timeout
        )
        system_prompt = self.binding.render_system_prompt()
        tools = _to_anthropic_tools(self.binding.tool_schemas)
        messages: list[dict[str, Any]] = [{"role": "user", "content": task.instruction}]
        tool_calls: list[ToolCall] = []
        final_answer: str | None = None
        turns = 0

        for turn in range(self.max_turns):
            turns = turn + 1
            try:
                response = await client.messages.create(
                    model=self.model,
                    max_tokens=_MAX_TOKENS,
                    system=system_prompt,
                    tools=tools,
                    messages=messages,
                )
            except Exception as exc:  # noqa: BLE001
                msg = str(exc) or type(exc).__name__
                lower = msg.lower()
                hint = ""
                if "authentication" in lower or "401" in lower or "403" in lower:
                    hint = " — Anthropic auth failed. Check ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL."
                elif "connection" in lower or "timeout" in lower:
                    hint = " — network error reaching the Anthropic-compatible endpoint."
                return TaskTrace(
                    task_id=task.task_id,
                    agent_name=self.name,
                    status="error",
                    turns=turns,
                    tool_calls=tuple(tool_calls),
                    elapsed_seconds=time.perf_counter() - start,
                    error=(msg + hint)[:1000],
                )

            # Echo the assistant turn back verbatim so the model keeps context.
            messages.append({"role": "assistant", "content": _blocks_to_dicts(response.content)})

            tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
            if not tool_uses:
                # No native tool_use block. Fall back to the JSON-action
                # protocol some bindings prescribe in their system prompt
                # (e.g. τ-bench: {"action": ..., "arguments": ...} per turn).
                text = _text_of(response.content)
                parsed = _parse_json(text)
                if "action" in parsed:
                    name = str(parsed["action"])
                    from ageneval.task.core.native_tools import execute_recorded_tool, openai_function

                    available = [
                        str(openai_function(s).get("name") or "")
                        for s in (self.binding.tool_schemas or [])
                        if openai_function(s).get("name")
                    ]
                    text = execute_recorded_tool(
                        tool_name=name,
                        kwargs=parsed.get("arguments") or {},
                        executor=self.binding.tool_executor,
                        initial_state=task.initial_state,
                        recorder=tool_calls,
                        available=available,
                    )
                    last = tool_calls[-1]
                    result = last.result if last.error is None else (last.result or {"error": last.error})
                    messages.append(
                        {
                            "role": "user",
                            "content": f"TOOL[{name}] result: {text}",
                        }
                    )
                    continue
                if "final_answer" in parsed:
                    final_answer = str(parsed["final_answer"])
                    break
                final_answer = text or None
                break

            # Native tool_use: execute every requested tool, feed results back.
            tool_results: list[dict[str, Any]] = []
            for block in tool_uses:
                from ageneval.task.core.native_tools import execute_recorded_tool, openai_function

                available = [
                    str(openai_function(s).get("name") or "")
                    for s in (self.binding.tool_schemas or [])
                    if openai_function(s).get("name")
                ]
                text = execute_recorded_tool(
                    tool_name=block.name,
                    kwargs=getattr(block, "input", {}) or {},
                    executor=self.binding.tool_executor,
                    initial_state=task.initial_state,
                    recorder=tool_calls,
                    available=available,
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": text,
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        elapsed = time.perf_counter() - start
        status = (
            "ok"
            if final_answer is not None
            else ("max_turns" if turns >= self.max_turns else "error")
        )
        return TaskTrace(
            task_id=task.task_id,
            agent_name=self.name,
            status=status,
            turns=turns,
            tool_calls=tuple(tool_calls),
            final_answer=final_answer,
            elapsed_seconds=elapsed,
        )


# ─── backwards-compat wrapper for τ-bench ─────────────────────────────────────


@dataclass
class ClaudeSDKTauAgent(ClaudeSDKAgent):
    """Thin wrapper: ``ClaudeSDKTauAgent(domain="retail")`` resolves the
    τ-bench binding automatically. New benchmarks should pass a custom
    ``AgentBinding`` directly to ``ClaudeSDKAgent``.
    """

    domain: str = "retail"
    binding: AgentBinding | None = None

    def __post_init__(self) -> None:  # type: ignore[override]
        if self.binding is None:
            from ageneval.task.datasets.tau_bench import build_tau_bench_binding

            self.binding = build_tau_bench_binding(self.domain)  # type: ignore[arg-type]
        super().__post_init__()

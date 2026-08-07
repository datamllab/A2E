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

_MAX_TURNS = 8
_MAX_TOKENS = 2048
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
    """Join every text block of an assistant message into one string."""
    parts: list[str] = []
    for block in content or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", "") or "")
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
        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        base_url = self.api_base or os.environ.get("ANTHROPIC_BASE_URL")

        if not api_key:
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="error",
                turns=0,
                elapsed_seconds=time.perf_counter() - start,
                error=(
                    "ClaudeSDKAgent requires ANTHROPIC_API_KEY. Set it (and "
                    "ANTHROPIC_BASE_URL for a self-hosted / gateway endpoint)."
                ),
            )

        assert self.binding is not None  # for type-checkers
        client = AsyncAnthropic(api_key=api_key, base_url=base_url or None)
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
                    args = dict(parsed.get("arguments") or {})
                    try:
                        result = self.binding.tool_executor(name, args, task.initial_state)
                        error = None
                    except Exception as exc:  # noqa: BLE001
                        result, error = {"error": str(exc)}, str(exc)
                    tool_calls.append(
                        ToolCall(name=name, arguments=args, result=result, error=error)
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": f"TOOL[{name}] result: {json.dumps(result, default=str)}",
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
                args = dict(getattr(block, "input", {}) or {})
                try:
                    result = self.binding.tool_executor(block.name, args, task.initial_state)
                    error = None
                except Exception as exc:  # noqa: BLE001
                    result, error = {"error": str(exc)}, str(exc)
                tool_calls.append(
                    ToolCall(name=block.name, arguments=args, result=result, error=error)
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
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

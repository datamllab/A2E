"""LangGraph node implementations — dataset-agnostic.

Each node wraps itself in an explicit OpenInference ``AGENT`` span so the
A2E UI surfaces three distinct agents per task (router / executor /
responder) instead of a generic CHAIN tree.

The nodes only know about the active ``AgentBinding`` (per-call argument).
Switching benchmarks therefore costs **one** new ``binding.py`` in
``task/datasets/<bench>/`` — these node files never change.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry import trace as trace_api

from ageneval.task.core import AgentBinding, TaskInput
from ageneval.task.core.native_tools import clip_for_model, openai_tool_dicts, unwrap_tool_kwargs

logger = logging.getLogger(__name__)

_AGENT_KIND_KEY = SpanAttributes.OPENINFERENCE_SPAN_KIND
_AGENT_KIND_VAL = OpenInferenceSpanKindValues.AGENT.value
_TOOL_KIND_VAL = OpenInferenceSpanKindValues.TOOL.value
_JSON_RE = re.compile(r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}", re.DOTALL)

_tracer = trace_api.get_tracer(__name__)


def router_node(*, state: dict[str, Any], llm: Any, binding: AgentBinding) -> dict[str, Any]:
    """ROUTER agent: picks the next tool call (or signals "done").

    Prefers native function-calling via ``bind_tools`` so the model sees the
    real JSON-Schema properties. Falls back to the legacy JSON-action text
    protocol only when the model returns no ``tool_calls``.
    """
    with _tracer.start_as_current_span("agent.router") as span:
        span.set_attribute(_AGENT_KIND_KEY, _AGENT_KIND_VAL)
        span.set_attribute("agent.name", "router")
        span.set_attribute("a2e.binding", binding.name)

        task: TaskInput = state["task"]
        history = state.get("tool_calls", [])
        system = binding.render_system_prompt()
        tool_dicts = openai_tool_dicts(binding.tool_schemas)
        tool_names = [str(d["function"]["name"]) for d in tool_dicts]
        user = _router_user_prompt(
            task=task,
            history=history,
            tool_names=tool_names,
            native_tools=bool(tool_dicts),
        )

        reply_text, native_calls = _invoke_llm_native(llm, system, user, tool_dicts, span)
        if native_calls:
            tc = native_calls[0]
            name = str(tc.get("name") or "")
            args = unwrap_tool_kwargs(tc.get("args") if isinstance(tc.get("args"), dict) else {})
            if name:
                return {"next_action": {"name": name, "arguments": args}}
        parsed = _parse_json(reply_text)
        if "action" in parsed:
            return {
                "next_action": {
                    "name": str(parsed["action"]),
                    "arguments": unwrap_tool_kwargs(parsed.get("arguments") or {}),
                },
            }
        if "final_answer" in parsed:
            return {"final_answer": str(parsed["final_answer"]), "next_action": None}
        if reply_text.strip():
            return {"final_answer": reply_text.strip(), "next_action": None}
        logger.warning("router got unstructured reply, terminating")
        return {"final_answer": "(no answer)", "next_action": None}


def executor_run(*, state: dict[str, Any], binding: AgentBinding) -> dict[str, Any]:
    """EXECUTOR agent: dispatches the chosen tool via ``binding.tool_executor``.

    The binding's ``tool_executor`` is the **only** dataset-specific code
    in this graph. Wrapped in its own AGENT span so the trace clearly
    shows when each tool ran.
    """
    action = state.get("next_action") or {}
    name = str(action.get("name") or "noop")
    args = action.get("arguments", {}) or {}
    task: TaskInput = state["task"]

    args_json = json.dumps(args, default=str)
    with _tracer.start_as_current_span("agent.executor") as span:
        span.set_attribute(_AGENT_KIND_KEY, _AGENT_KIND_VAL)
        span.set_attribute("agent.name", "executor")
        # Nested TOOL-kind span so A2E renders the tool call as a
        # first-class step in the trajectory (with input / output panels),
        # not just opaque attributes on the executor agent span.
        with _tracer.start_as_current_span(f"tool.{name}") as tool_span:
            tool_span.set_attribute(_AGENT_KIND_KEY, _TOOL_KIND_VAL)
            tool_span.set_attribute(SpanAttributes.TOOL_NAME, name)
            tool_span.set_attribute(SpanAttributes.TOOL_PARAMETERS, args_json)
            tool_span.set_attribute(SpanAttributes.INPUT_VALUE, args_json)
            try:
                from ageneval.task.core.native_tools import execute_recorded_tool, openai_function
                from ageneval.task.core.result import ToolCall

                tmp: list[ToolCall] = [
                    ToolCall(
                        name=str(tc.get("name") or ""),
                        arguments=dict(tc.get("arguments") or {}),
                        result=tc.get("result"),
                    )
                    for tc in (state.get("tool_calls") or [])
                ]
                available = [
                    str(openai_function(s).get("name") or "")
                    for s in (binding.tool_schemas or [])
                    if openai_function(s).get("name")
                ]
                text = execute_recorded_tool(
                    tool_name=name,
                    kwargs=args if isinstance(args, dict) else {},
                    executor=binding.tool_executor,
                    initial_state=task.initial_state,
                    recorder=tmp,
                    available=available,
                )
                last = tmp[-1] if tmp else None
                result = (
                    last.result
                    if last is not None and last.error is None
                    else (last.result if last is not None else {"error": text})
                )
                if last is not None and last.error:
                    result = last.result or {"error": last.error}
            except Exception as exc:  # noqa: BLE001
                tool_span.record_exception(exc)
                span.record_exception(exc)
                result = {"error": str(exc)}
            result_json = json.dumps(result, default=str)
            tool_span.set_attribute(SpanAttributes.OUTPUT_VALUE, result_json)
        span.set_attribute("tool.name", name)
        span.set_attribute("tool.parameters", args_json)
        span.set_attribute("tool.result", result_json)

    tool_calls = list(state.get("tool_calls", []))
    tool_calls.append({"name": name, "arguments": args, "result": result})
    return {
        "tool_calls": tool_calls,
        "next_action": None,
        "turns": int(state.get("turns", 0)) + 1,
    }


def responder_node(*, state: dict[str, Any], llm: Any) -> dict[str, Any]:
    """RESPONDER agent: composes the final natural-language answer."""
    with _tracer.start_as_current_span("agent.responder") as span:
        span.set_attribute(_AGENT_KIND_KEY, _AGENT_KIND_VAL)
        span.set_attribute("agent.name", "responder")

        existing = state.get("final_answer")
        if existing and str(existing).strip() not in {"(no answer)", "assistant:", "assistant"}:
            return {"final_answer": existing}

        task: TaskInput = state["task"]
        history = state.get("tool_calls", [])
        system = (
            "You are the responder. Produce the final answer for this task "
            "from the instruction and tool results. Do not invent tool calls."
        )
        user = (
            f"Task: {task.instruction}\n"
            f"Tool calls made: {clip_for_model(_public_history(history), max_chars=6000)}\n"
            "Write the final answer only."
        )
        text = _invoke_llm(llm, system, user, span)
        return {"final_answer": text.strip() or "(no answer)"}


# ─── helpers ──────────────────────────────────────────────────────────────────


def _invoke_llm(llm: Any, system: str, user: str, span: trace_api.Span) -> str:
    try:
        return _complete_plain(llm, system, user)
    except Exception as exc:  # noqa: BLE001
        span.record_exception(exc)
        raise


def _invoke_llm_native(
    llm: Any,
    system: str,
    user: str,
    tool_dicts: list[dict[str, Any]],
    span: trace_api.Span,
) -> tuple[str, list[dict[str, Any]]]:
    """One router turn. Binds native OpenAI schemas when present; never re-invokes."""
    if not tool_dicts:
        try:
            return _complete_plain(llm, system, user), []
        except Exception as exc:  # noqa: BLE001
            span.record_exception(exc)
            raise
    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    try:
        ai_msg = llm.bind_tools(tool_dicts).invoke(messages)
    except Exception as exc:  # noqa: BLE001
        span.record_exception(exc)
        raise
    text = _message_text(ai_msg)
    calls = list(getattr(ai_msg, "tool_calls", None) or [])
    if not text and not calls:
        text = _complete_plain(llm, system, user)
    return text, calls


def _complete_plain(llm: Any, system: str, user: str) -> str:
    """Chat completion that keeps kimi-k3 ``reasoning_content``.

    ``langchain_openai.ChatOpenAI`` drops hidden reasoning and can return
    ``content=""`` with ``finish_reason=length`` after 4096 thinking tokens.
    The official OpenAI client still exposes that text on the message.
    """
    from openai import OpenAI

    from ageneval.task.core.budget import llm_timeout, max_tokens

    model = getattr(llm, "model_name", None) or getattr(llm, "model", None) or "kimi/kimi-k3"
    key = getattr(llm, "openai_api_key", None)
    if hasattr(key, "get_secret_value"):
        key = key.get_secret_value()
    base = (
        getattr(llm, "openai_api_base", None)
        or getattr(llm, "base_url", None)
        or os.environ.get("OPENAI_API_BASE")
    )
    client = OpenAI(
        api_key=str(key or os.environ.get("OPENAI_API_KEY") or ""),
        base_url=str(base) if base else None,
        timeout=llm_timeout(),
    )
    resp = client.chat.completions.create(
        model=str(model),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens(),
    )
    msg = resp.choices[0].message
    text = (msg.content or "").strip()
    if text:
        return text
    dump = msg.model_dump() if hasattr(msg, "model_dump") else {}
    for key_name in ("reasoning_content", "reasoning", "thinking"):
        extra = dump.get(key_name)
        if extra:
            return str(extra).strip()
    nested = dump.get("model_extra") or {}
    if isinstance(nested, dict):
        for key_name in ("reasoning_content", "reasoning", "thinking"):
            extra = nested.get(key_name)
            if extra:
                return str(extra).strip()
    return ""


def _message_text(msg: Any) -> str:
    """Visible reply, or kimi-k3 thinking if ``content`` is empty."""
    content = getattr(msg, "content", "") or ""
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text") or block.get("thinking") or block.get("reasoning_content")
                if text:
                    parts.append(str(text))
        joined = "".join(parts).strip()
        if joined:
            return joined
    elif str(content).strip():
        return str(content)
    extra = getattr(msg, "additional_kwargs", None) or {}
    if isinstance(extra, dict):
        for key in ("reasoning_content", "thinking", "text"):
            text = extra.get(key)
            if text:
                return str(text).strip()
    return str(content or "")


def _router_user_prompt(
    *,
    task: TaskInput,
    history: list[dict[str, Any]],
    tool_names: list[str] | None = None,
    native_tools: bool = False,
) -> str:
    available = ", ".join(tool_names or []) or "(none)"
    state_for_prompt = _public_state(task.initial_state)
    history_for_prompt = _public_history(history)
    if native_tools:
        return (
            f"Task: {task.instruction}\n"
            f"Initial state: {json.dumps(state_for_prompt, default=str)}\n"
            f"History so far: {json.dumps(history_for_prompt, default=str)}\n"
            f"Available tools: {available}\n"
            "Call a tool via the function-calling interface with its named arguments. "
            "Do not emit a JSON action object as plain text and do not wrap "
            "arguments in arguments_json. "
            "When finished, reply to the customer in plain language with no tool call."
        )
    tool_policy = (
        "Use an available tool before finishing when a tool can advance the task.\n"
        if tool_names
        else ""
    )
    return (
        f"Task: {task.instruction}\n"
        f"Initial state: {json.dumps(state_for_prompt, default=str)}\n"
        f"History so far: {json.dumps(history_for_prompt, default=str)}\n"
        f"Available action names: {available}\n"
        f"{tool_policy}"
        "Return exactly one JSON object with no prose or Markdown.\n"
        'To call a tool, return {"action":"<available action name>",'
        '"arguments":{...}}.\n'
        'To finish, return {"final_answer":"<answer>"}.\n'
        "Pick the next action."
    )


def _public_state(state: Any) -> Any:
    """Drop the live τ-bench DB deepcopy so the prompt stays small."""
    if not isinstance(state, dict):
        return state
    return {k: v for k, v in state.items() if not str(k).startswith("__")}


def _public_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in history:
        row = {
            "name": item.get("name"),
            "arguments": item.get("arguments"),
            "result": item.get("result"),
        }
        if isinstance(row["result"], dict):
            row["result"] = {k: v for k, v in row["result"].items() if not str(k).startswith("__")}
        row["result"] = clip_for_model(row["result"])
        out.append(row)
    return out


def _parse_json(text: str) -> dict[str, Any]:
    match = _JSON_RE.search(text or "")
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}

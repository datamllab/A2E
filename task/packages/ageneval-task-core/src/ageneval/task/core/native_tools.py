"""Convert OpenAI-format tool schemas into native per-harness callables.

Several agent SDKs (openai-agents, google-adk, llama-index, crewai, autogen)
build the *model-facing* tool schema from a Python function signature. If the
wrapper only accepts ``arguments_json: str``, the model sees an empty/opaque
schema, guesses arguments, and produces long vacuous trajectories.

This module keeps the dataset schema (``function.parameters``) intact and
exposes it as keyword arguments so each harness advertises the real properties.
"""

from __future__ import annotations

import inspect
import json
import os
import urllib.parse
from collections.abc import Mapping, Sequence
from typing import Any, Callable

# Tool results go back into the next native model turn. Unbounded pages
# (DeepSearchQA open_url) blow the gateway context and look like a schema
# failure. Recorder keeps the full object; only the model-facing string is cut.
_MODEL_RESULT_CHARS = int(os.environ.get("A2E_TOOL_RESULT_CHARS", "2500"))

from ageneval.task.core.binding import AgentBinding
from ageneval.task.core.dataset import TaskInput
from ageneval.task.core.result import ToolCall

_JSON_TO_PY: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def openai_function(schema: Mapping[str, Any]) -> dict[str, Any]:
    fn = schema.get("function") if isinstance(schema.get("function"), Mapping) else schema
    return dict(fn or {})


def parameters_block(schema: Mapping[str, Any]) -> dict[str, Any]:
    fn = openai_function(schema)
    params = fn.get("parameters") or {"type": "object", "properties": {}}
    if not isinstance(params, dict):
        params = {"type": "object", "properties": {}}
    params.setdefault("type", "object")
    params.setdefault("properties", {})
    return params


def schema_is_empty(schema: Mapping[str, Any]) -> bool:
    """True when the tool advertises no properties (the original A2E stub bug).

    A *legitimate* zero-argument tool has ``properties: {}`` without
    ``additionalProperties: true``. The old stub marked every tool as
    free-form (``additionalProperties: true``), which is what we reject.
    """
    params = parameters_block(schema)
    props = params.get("properties") or {}
    if isinstance(props, dict) and props:
        return False
    return params.get("additionalProperties") is True


def clip_for_model(value: Any, *, max_chars: int | None = None) -> str:
    """Serialize a tool result for the next model turn, with a hard char cap."""
    limit = _MODEL_RESULT_CHARS if max_chars is None else max_chars
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, default=str)
        except Exception:  # noqa: BLE001
            text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + f"...[truncated {len(text) - limit} chars]"


def unwrap_tool_kwargs(kwargs: Mapping[str, Any]) -> dict[str, Any]:
    """Recover real args if a model nested them under a single wrapper key."""
    args = dict(kwargs)
    if len(args) != 1:
        return args
    only_key, only_val = next(iter(args.items()))
    if only_key in ("kwargs", "arguments", "args") and isinstance(only_val, dict):
        return dict(only_val)
    if only_key == "arguments_json" and isinstance(only_val, str):
        try:
            parsed = json.loads(only_val or "{}")
        except (ValueError, TypeError):
            return args
        if isinstance(parsed, dict):
            return parsed
    return args


def canonicalize_url(url: str) -> str:
    """Collapse URL variants the model retries as if they were new pages.

    ``.../current/``, ``.../current/default.htm`` and host-case changes are
    the same fetch. Do not lowercase the path — some official sites are
    case-sensitive.
    """
    raw = (url or "").strip()
    parts = urllib.parse.urlsplit(raw)
    path = parts.path or "/"
    lower = path.lower()
    for leaf in ("/default.htm", "/default.html", "/index.html", "/index.htm"):
        if lower.endswith(leaf):
            path = path[: -len(leaf)] or "/"
            break
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urllib.parse.urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, parts.query, "")
    )


def canonicalize_tool_args(name: str, args: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(args)
    if isinstance(out.get("query"), str):
        out["query"] = " ".join(out["query"].split()).strip()
    if isinstance(out.get("url"), str) and out["url"].startswith(("http://", "https://")):
        out["url"] = canonicalize_url(out["url"])
    return out


def _canon_call(name: str, args: Mapping[str, Any]) -> str:
    return json.dumps(
        {"name": name, "arguments": canonicalize_tool_args(name, args)},
        sort_keys=True,
        default=str,
    )


def execute_recorded_tool(
    *,
    tool_name: str,
    kwargs: Mapping[str, Any],
    executor: Any,
    initial_state: Mapping[str, Any],
    recorder: list[ToolCall],
    available: Sequence[str] | None = None,
) -> str:
    """Run one tool with shared unwrap / unknown-name / duplicate-call guards.

    Identical ``(name, args)`` is not re-executed: the model gets a short
    duplicate notice instead of another network/DB hit. That stops the
    open_url/web_search loops that look like schema failures and blow the
    outer timeout. Trajectory still records the duplicate attempt.
    """
    args = canonicalize_tool_args(tool_name, unwrap_tool_kwargs(kwargs))
    names = [str(n) for n in (available or ())]
    if names and tool_name not in names:
        payload = {"error": f"unknown tool '{tool_name}'", "available": names}
        recorder.append(
            ToolCall(name=tool_name, arguments=args, result=payload, error=payload["error"])
        )
        return clip_for_model(payload)

    key = _canon_call(tool_name, args)
    if any(_canon_call(tc.name, tc.arguments or {}) == key for tc in recorder):
        payload = {
            "error": "duplicate tool call; reuse the previous result instead of calling again",
            "tool": tool_name,
            "arguments": args,
        }
        recorder.append(ToolCall(name=tool_name, arguments=args, result=payload, error=payload["error"]))
        return clip_for_model(payload)

    try:
        result = executor(tool_name, args, initial_state)
    except Exception as exc:  # noqa: BLE001
        recorder.append(ToolCall(name=tool_name, arguments=args, result=None, error=str(exc)))
        return clip_for_model({"error": str(exc)})
    recorder.append(ToolCall(name=tool_name, arguments=args, result=result))
    return clip_for_model(result)


def _binding_tool_names(binding: AgentBinding) -> list[str]:
    names: list[str] = []
    for schema in binding.tool_schemas or ():
        fn = openai_function(schema)
        n = fn.get("name")
        if n:
            names.append(str(n))
    return names


def invoke_binding_tool(
    *,
    tool_name: str,
    kwargs: Mapping[str, Any],
    binding: AgentBinding,
    task: TaskInput,
    recorder: list[ToolCall],
) -> str:
    return execute_recorded_tool(
        tool_name=tool_name,
        kwargs=kwargs,
        executor=binding.tool_executor,
        initial_state=task.initial_state,
        recorder=recorder,
        available=_binding_tool_names(binding),
    )


def _annotation_for(spec: Mapping[str, Any]) -> type:
    raw = spec.get("type", "string") if isinstance(spec, Mapping) else "string"
    if isinstance(raw, list):
        raw = raw[0] if raw else "string"
    return _JSON_TO_PY.get(str(raw), str)


def attach_json_schema_signature(
    fn: Callable[..., Any],
    *,
    name: str,
    description: str,
    parameters: Mapping[str, Any],
) -> Callable[..., Any]:
    """Rewrite ``fn``'s inspect signature to match JSON-Schema properties.

    Decorator-based SDKs (openai-agents ``function_tool``, google-adk
    ``FunctionTool``, LlamaIndex ``FunctionTool``) read this signature to
    publish the model-facing schema.
    """
    props = parameters.get("properties") or {}
    required = set(parameters.get("required") or [])
    params: list[inspect.Parameter] = []
    annotations: dict[str, Any] = {"return": str}
    doc_args: list[str] = []
    # Legitimate zero-arg tools (e.g. list_all_product_types) have empty
    # properties without additionalProperties:true. Do NOT invent an
    # arguments_json field — that is the original schema-flattening bug.
    if (not isinstance(props, dict) or not props) and parameters.get(
        "additionalProperties"
    ) is True:
        params.append(
            inspect.Parameter(
                "arguments_json",
                inspect.Parameter.KEYWORD_ONLY,
                default="{}",
                annotation=str,
            )
        )
        annotations["arguments_json"] = str
        doc_args.append("    arguments_json: JSON object string of arguments.")
    elif isinstance(props, dict) and props:
        for pname, spec in props.items():
            if not str(pname).isidentifier():
                continue
            spec_map = spec if isinstance(spec, Mapping) else {}
            anno = _annotation_for(spec_map)
            default = inspect.Parameter.empty if pname in required else None
            params.append(
                inspect.Parameter(
                    str(pname),
                    inspect.Parameter.KEYWORD_ONLY,
                    default=default,
                    annotation=anno,
                )
            )
            annotations[str(pname)] = anno
            desc = str(spec_map.get("description") or pname)
            doc_args.append(f"    {pname}: {desc}")
    fn.__name__ = name
    fn.__qualname__ = name
    fn.__signature__ = inspect.Signature(params, return_annotation=str)  # type: ignore[attr-defined]
    fn.__annotations__ = annotations
    fn.__doc__ = (description or f"Invoke the {name} tool.") + (
        "\n\nArgs:\n" + "\n".join(doc_args) if doc_args else ""
    )
    return fn


def make_kwargs_tool(
    *,
    schema: Mapping[str, Any],
    binding: AgentBinding,
    task: TaskInput,
    recorder: list[ToolCall],
) -> Callable[..., str]:
    """Return a ``**kwargs`` callable whose signature matches the JSON schema."""
    fn = openai_function(schema)
    name = str(fn.get("name") or "tool")
    description = str(fn.get("description") or f"Invoke the {name} tool.")
    parameters = parameters_block(schema)

    def _tool(**kwargs: Any) -> str:
        return invoke_binding_tool(
            tool_name=name,
            kwargs=kwargs,
            binding=binding,
            task=task,
            recorder=recorder,
        )

    return attach_json_schema_signature(
        _tool, name=name, description=description, parameters=parameters
    )


def pydantic_args_model(name: str, parameters: Mapping[str, Any]) -> type:
    """Build a pydantic v2 model from a JSON-Schema parameters block (crewai)."""
    from pydantic import BaseModel, Field, create_model

    props = parameters.get("properties") or {}
    required = set(parameters.get("required") or [])
    fields: dict[str, tuple[Any, Any]] = {}
    if (not isinstance(props, dict) or not props) and parameters.get(
        "additionalProperties"
    ) is True:
        fields["arguments_json"] = (
            str,
            Field(default="{}", description="JSON object string of arguments."),
        )
    elif isinstance(props, dict) and props:
        for pname, spec in props.items():
            if not str(pname).isidentifier():
                continue
            spec_map = spec if isinstance(spec, Mapping) else {}
            anno = _annotation_for(spec_map)
            desc = str(spec_map.get("description") or pname)
            if pname in required:
                fields[str(pname)] = (anno, Field(..., description=desc))
            else:
                fields[str(pname)] = (anno | None, Field(default=None, description=desc))
    return create_model(f"{name}Args", **fields, __base__=BaseModel)  # type: ignore[call-overload]


def openai_tool_dicts(schemas: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """LangChain ``bind_tools`` accepts OpenAI-format dicts."""
    out: list[dict[str, Any]] = []
    for schema in schemas:
        fn = openai_function(schema)
        if not fn.get("name"):
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": fn["name"],
                    "description": fn.get("description") or "",
                    "parameters": parameters_block(schema),
                },
            }
        )
    return out

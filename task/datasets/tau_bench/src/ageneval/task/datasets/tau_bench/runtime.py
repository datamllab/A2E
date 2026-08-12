"""Live τ-bench environment: real tool schemas, wiki policy, and mutable DB.

The previous adapter only exposed tool *names* (empty parameter schemas) and
acknowledged every call. Harnesses then either invented arguments or called
ten-plus tools against an empty world. This module wraps the official Sierra
retail/airline tools and databases so each call mutates a per-task deepcopy.
"""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from typing import Any, Literal, Mapping

Domain = Literal["retail", "airline"]

_DB_KEY = "__tau_db__"
_DOMAIN_KEY = "__tau_domain__"

_NATIVE_TOOL_SUFFIX = (
    "\n\nYou have the tools listed in the function-calling interface. "
    "Call a tool by invoking the function with its named arguments. "
    "Do not emit a JSON action object as plain text. "
    "Identify the user first (email or name+zip) before changing any records. "
    "When the request is complete, reply to the customer in plain language."
)


@lru_cache(maxsize=2)
def load_domain_data(domain: Domain) -> dict[str, Any]:
    if domain == "airline":
        from ageneval.task.datasets.tau_bench.upstream.airline.data import load_data
    else:
        from ageneval.task.datasets.tau_bench.upstream.retail.data import load_data
    return load_data()


def get_tool_classes(domain: Domain):
    if domain == "airline":
        from ageneval.task.datasets.tau_bench.upstream.airline.tools import ALL_TOOLS
    else:
        from ageneval.task.datasets.tau_bench.upstream.retail.tools import ALL_TOOLS
    return ALL_TOOLS


def get_wiki(domain: Domain) -> str:
    if domain == "airline":
        from ageneval.task.datasets.tau_bench.upstream.airline.wiki import WIKI
    else:
        from ageneval.task.datasets.tau_bench.upstream.retail.wiki import WIKI
    return WIKI


def get_tool_schemas(domain: Domain | None = "retail") -> list[dict[str, Any]]:
    """OpenAI-style schemas with real parameter names, types, and required fields."""
    resolved: Domain = "airline" if domain == "airline" else "retail"
    return [cls.get_info() for cls in get_tool_classes(resolved)]


def build_system_prompt(domain: Domain) -> str:
    return get_wiki(domain).rstrip() + _NATIVE_TOOL_SUFFIX


def _tool_map(domain: Domain) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for cls in get_tool_classes(domain):
        name = cls.get_info()["function"]["name"]
        mapping[name] = cls
    return mapping


def ensure_db(state: Mapping[str, Any], domain: Domain) -> dict[str, Any]:
    """Return the mutable per-task database, creating it on first use.

    The full retail/airline DB is a few megabytes, so it is *not* serialized
    into every uploaded example. The executor lazily deep-copies the template
    into ``state['__tau_db__']`` which is shared across tool calls of one run.
    """
    if isinstance(state, dict):
        db = state.get(_DB_KEY)
        if isinstance(db, dict):
            return db
        db = deepcopy(load_domain_data(domain))
        state[_DB_KEY] = db
        state[_DOMAIN_KEY] = domain
        return db
    return deepcopy(load_domain_data(domain))


def execute_tool(
    name: str,
    arguments: Mapping[str, Any],
    state: Mapping[str, Any],
    domain: Domain = "retail",
) -> Any:
    """Dispatch ``name`` against the official Sierra tool implementation."""
    tools = _tool_map(domain)
    if name not in tools:
        return {"error": f"unknown tool '{name}'", "available": sorted(tools)}
    db = ensure_db(state, domain)
    args = dict(arguments or {})
    try:
        result = tools[name].invoke(data=db, **args)
    except TypeError as exc:
        return {"error": f"invalid arguments for {name}: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    if isinstance(result, str):
        text = result.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except (ValueError, TypeError):
                return text
        return text
    return result

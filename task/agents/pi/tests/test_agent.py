from __future__ import annotations

import json
import tempfile
from urllib import request

from ageneval.task.agents.pi.agent import (
    _attribute,
    _binding_tool_definitions,
    _BindingBridge,
    _span_kind,
    _trace_id_from_traceparent,
)
from ageneval.task.core import AgentBinding


def _binding(calls: list[tuple[str, dict, dict]]) -> AgentBinding:
    def execute(name, arguments, state):
        calls.append((name, dict(arguments), dict(state)))
        return {"answer": arguments["value"] + state["offset"]}

    return AgentBinding(
        name="bridge-test",
        tool_schemas=(
            {
                "type": "function",
                "function": {
                    "name": "add_offset",
                    "description": "Add the task offset.",
                    "parameters": {
                        "type": "object",
                        "properties": {"value": {"type": "integer"}},
                        "required": ["value"],
                    },
                },
            },
        ),
        tool_executor=execute,
        system_prompt_builder=lambda _tools: "Use the benchmark tool.",
    )


def test_binding_bridge_calls_the_existing_a2e_executor() -> None:
    calls: list[tuple[str, dict, dict]] = []
    binding = _binding(calls)
    with tempfile.TemporaryDirectory() as directory:
        with _BindingBridge(binding, {"offset": 2}, directory) as config_path:
            config = json.loads(open(config_path, encoding="utf-8").read())
            http_request = request.Request(
                config["endpoint"],
                data=json.dumps({"name": "add_offset", "arguments": {"value": 3}}).encode(),
                headers={
                    "authorization": f"Bearer {config['token']}",
                    "content-type": "application/json",
                },
                method="POST",
            )
            with request.urlopen(http_request) as response:
                assert json.loads(response.read()) == {"result": {"answer": 5}}

    assert calls == [("add_offset", {"value": 3}, {"offset": 2})]
    assert config["tools"] == _binding_tool_definitions(binding)
    assert "native function tools" in config["systemPrompt"]


def test_span_helpers_accept_server_and_flat_attribute_shapes() -> None:
    traceparent = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    assert _trace_id_from_traceparent(traceparent) == "0123456789abcdef0123456789abcdef"
    assert _trace_id_from_traceparent("invalid") is None
    assert _attribute({"tool.name": "bash"}, "tool.name") == "bash"
    assert _attribute({"tool": {"name": "bash"}}, "tool.name") == "bash"
    assert _span_kind({"attributes": {"openinference": {"span": {"kind": "tool"}}}}) == "TOOL"

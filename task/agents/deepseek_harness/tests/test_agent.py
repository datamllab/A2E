from __future__ import annotations

import asyncio
import json
import tempfile
from urllib import request

import ageneval.task.agents.deepseek_harness.agent as agent_module
import httpx
from ageneval.task.agents.deepseek_harness.agent import (
    DeepSeekHarnessAgent,
    _attribute,
    _binding_tool_definitions,
    _BindingBridge,
    _provider_api_base,
    _provider_api_key,
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


def _empty_binding() -> AgentBinding:
    return AgentBinding(
        name="no-tools",
        tool_schemas=(),
        tool_executor=lambda *_args: None,
        system_prompt_builder=lambda _tools: "Answer directly.",
    )


def test_binding_bridge_calls_existing_executor() -> None:
    calls: list[tuple[str, dict, dict]] = []
    binding = _binding(calls)
    with tempfile.TemporaryDirectory() as directory:
        with _BindingBridge(binding, {"offset": 2}, directory) as config_path:
            config = json.loads(open(config_path, encoding="utf-8").read())
            http_request = request.Request(
                config["endpoint"],
                data=json.dumps(
                    {"name": "add_offset", "arguments": {"value": 3}}
                ).encode(),
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


def test_empty_binding_has_no_bridge_tools() -> None:
    assert _binding_tool_definitions(_empty_binding()) == []


def test_provider_credentials_support_openai_compatible_environment(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "compatible-key")
    monkeypatch.setenv("OPENAI_API_BASE", "https://example.test/v1")

    assert _provider_api_key(None) == "deepseek-key"
    assert (
        _provider_api_key(None, api_base="https://example.test/v1")
        == "compatible-key"
    )
    assert _provider_api_base(None) == "https://example.test/v1"
    assert _provider_api_key("explicit-key", api_base="https://example.test/v1") == "explicit-key"
    assert _provider_api_base("https://explicit.test/v1") == "https://explicit.test/v1"


def test_span_helpers_accept_server_and_flat_shapes() -> None:
    traceparent = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    assert _trace_id_from_traceparent(traceparent) == "0123456789abcdef0123456789abcdef"
    assert _trace_id_from_traceparent("invalid") is None
    assert _attribute({"tool.name": "bash"}, "tool.name") == "bash"
    assert _attribute({"tool": {"name": "bash"}}, "tool.name") == "bash"
    assert _span_kind(
        {"attributes": {"openinference": {"span": {"kind": "tool"}}}}
    ) == "TOOL"


def test_collect_span_stats_retries_a_transient_timeout(monkeypatch) -> None:
    trace_id = "0123456789abcdef0123456789abcdef"
    spans = [
        {"id": "agent", "context": {"trace_id": trace_id}, "span_kind": "AGENT"},
        {"id": "llm", "context": {"trace_id": trace_id}, "span_kind": "LLM"},
        {
            "id": "tool",
            "context": {"trace_id": trace_id},
            "span_kind": "TOOL",
            "name": "deepseek-harness.tool bash",
            "status_code": "OK",
            "attributes": {
                "tool.name": "bash",
                "input.value": '{"command":"pwd"}',
                "output.value": "ok",
            },
        },
    ]

    class Response:
        def raise_for_status(self) -> None:
            return

        def json(self) -> dict:
            return {"data": spans}

    class Client:
        calls = 0

        def __init__(self, **_kwargs) -> None:
            return

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc_info) -> None:
            return

        async def get(self, _url, **_kwargs):
            Client.calls += 1
            if Client.calls == 1:
                raise httpx.ReadTimeout("busy collector")
            return Response()

    async def no_sleep(_seconds: float) -> None:
        return

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    monkeypatch.setattr(agent_module.asyncio, "sleep", no_sleep)
    monkeypatch.setenv("A2E_PROJECT_NAME", "retry-test")
    runner = DeepSeekHarnessAgent(binding=_binding([]), dsh_command=["dsh"])

    turns, tool_calls = asyncio.run(
        runner._collect_span_stats(
            f"00-{trace_id}-0123456789abcdef-01"
        )
    )

    assert Client.calls == 4
    assert turns == 1
    assert len(tool_calls) == 1
    assert tool_calls[0].name == "bash"
    assert tool_calls[0].arguments == {"command": "pwd"}

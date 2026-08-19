from __future__ import annotations

import asyncio
import json
import tempfile
from types import SimpleNamespace
from urllib import request

from ageneval.task.agents.pi.agent import (
    PiAgent,
    _attribute,
    _binding_tool_definitions,
    _BindingBridge,
    _container_endpoint,
    _custom_models_config,
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


def test_openai_compatible_provider_config_uses_environment_credentials(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "compatible-key")
    monkeypatch.setenv("OPENAI_API_BASE", "https://example.test/v1")

    assert _provider_api_key(None, "deepseek") == "compatible-key"
    assert _provider_api_base(None) == "https://example.test/v1"
    config = _custom_models_config("qwen-test", "https://example.test/v1")
    provider = config["providers"]["a2e-openai-compatible"]
    assert provider["apiKey"] == "$A2E_PI_PROVIDER_API_KEY"
    assert provider["models"][0]["id"] == "qwen-test"
    assert "compatible-key" not in json.dumps(config)


def test_run_in_sandbox_uses_native_pi_tools_and_container_collector(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class Sandbox:
        workdir = "/workspace"

        def write_file(self, path, contents) -> None:
            calls["write"] = (path, contents)

        def exec(self, command, **kwargs):
            calls["command"] = command
            calls["kwargs"] = kwargs
            return SimpleNamespace(
                stdout="completed",
                stderr="",
                success=True,
                returncode=0,
            )

    runner = PiAgent(
        binding=_binding([]),
        model="qwen-test",
        api_base="https://example.test/v1",
        api_key="secret",
        pi_cli="pi",
        monitor_extension=None,
    )

    async def collect(_traceparent):
        return 1, []

    monkeypatch.setattr(runner, "_collect_span_stats", collect)
    monkeypatch.setattr(runner, "_current_traceparent", lambda: None)
    monkeypatch.setenv("A2E_COLLECTOR_ENDPOINT", "http://127.0.0.1:6106")
    monkeypatch.delenv("A2E_PI_DISABLE_BUILTIN_TOOLS", raising=False)
    trace = asyncio.run(
        runner.run_in_sandbox(
            SimpleNamespace(task_id="task", instruction="Fix it"),
            Sandbox(),
        )
    )

    command = calls["command"]
    kwargs = calls["kwargs"]
    assert "--no-builtin-tools" not in command
    assert "--no-tools" not in command
    assert "/opt/a2e-harness/dist/extensions/a2e-monitor.js" in command
    assert kwargs["cwd"] == "/workspace"
    assert kwargs["env"]["A2E_COLLECTOR_ENDPOINT"] == "http://host.docker.internal:6106"
    assert kwargs["env"]["A2E_PI_PROVIDER_API_KEY"] == "secret"
    assert calls["write"][0] == "/tmp/a2e-pi-agent/models.json"
    assert trace.status == "ok"
    assert trace.raw["harness_location"] == "sandbox"


def test_container_endpoint_preserves_remote_hosts() -> None:
    assert _container_endpoint("http://localhost:6006") == "http://host.docker.internal:6006"
    assert _container_endpoint("https://collector.example/v1") == "https://collector.example/v1"

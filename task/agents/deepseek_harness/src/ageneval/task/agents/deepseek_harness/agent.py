"""Dataset-agnostic A2E runner for the DeepSeek Harness headless CLI."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import shlex
import shutil
import tempfile
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ageneval.task.core import AgentBinding, AgentRunner, TaskInput, TaskTrace, ToolCall

_DEFAULT_MODEL = os.environ.get("A2E_MODEL") or "deepseek-v4-flash"
_RUN_DEADLINE = float(os.environ.get("A2E_DEEPSEEK_DEADLINE", "900"))


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists() or (parent / "monitor").is_dir():
            return parent
    return here.parents[0]


def _resolve_dsh_command() -> list[str]:
    custom = os.environ.get("A2E_DEEPSEEK_CLI")
    if custom:
        return shlex.split(custom, posix=os.name != "nt")
    executable = shutil.which("dsh")
    if executable and not executable.lower().endswith((".cmd", ".bat")):
        return [executable]
    local_cli = (
        _repo_root()
        / "monitor"
        / "instrumentation-js"
        / "a2e-deepseek-harness-monitor"
        / "node_modules"
        / "@deepseek-ai"
        / "dsh"
        / "lib"
        / "bin.js"
    )
    node = shutil.which("node")
    if node and local_cli.is_file():
        return [node, str(local_cli)]
    raise RuntimeError(
        "DeepSeek Harness CLI not found. Set A2E_DEEPSEEK_CLI, install "
        "@deepseek-ai/dsh, or install dependencies in the DeepSeek monitor package."
    )


def _binding_tool_definitions(binding: AgentBinding) -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    for schema in binding.tool_schemas:
        function = schema.get("function", schema)
        if not isinstance(function, Mapping) or not function.get("name"):
            continue
        definitions.append(
            {
                "name": str(function["name"]),
                "description": str(function.get("description", "")),
                "parameters": dict(
                    function.get("parameters")
                    or {"type": "object", "properties": {}}
                ),
            }
        )
    return definitions


class _BindingBridge:
    """Delegate native Harness tool calls to the selected A2E AgentBinding."""

    def __init__(self, binding: AgentBinding, state: Mapping[str, Any], directory: str) -> None:
        self.binding = binding
        self.state = state
        self.directory = directory
        self.token = secrets.token_urlsafe(32)
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.config_path = Path(directory) / "a2e-deepseek-binding.json"

    def __enter__(self) -> str:
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if (
                    self.path != "/tool"
                    or self.headers.get("authorization") != f"Bearer {bridge.token}"
                ):
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers.get("content-length", "0"))
                    request = json.loads(self.rfile.read(length) or b"{}")
                    name = str(request.get("name", ""))
                    arguments = request.get("arguments") or {}
                    if not isinstance(arguments, Mapping):
                        raise TypeError("tool arguments must be an object")
                    result = bridge.binding.tool_executor(name, arguments, bridge.state)
                    payload = json.dumps(
                        {"result": result}, ensure_ascii=False, default=str
                    ).encode()
                    self.send_response(200)
                except Exception as exc:
                    payload = json.dumps({"error": str(exc) or type(exc).__name__}).encode()
                    self.send_response(500)
                self.send_header("content-type", "application/json; charset=utf-8")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, _format: str, *_args: Any) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        port = self.server.server_address[1]
        self.config_path.write_text(
            json.dumps(
                {
                    "endpoint": f"http://127.0.0.1:{port}/tool",
                    "token": self.token,
                    "tools": _binding_tool_definitions(self.binding),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return str(self.config_path)

    def __exit__(self, *_exc_info: object) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=2)


def _trace_id_from_traceparent(traceparent: str | None) -> str | None:
    if not traceparent:
        return None
    parts = traceparent.split("-")
    return parts[1] if len(parts) == 4 and len(parts[1]) == 32 else None


def _attribute(attributes: Mapping[str, Any], name: str) -> Any:
    if name in attributes:
        return attributes[name]
    value: Any = attributes
    for part in name.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def _span_kind(span: Mapping[str, Any]) -> str | None:
    value = span.get("span_kind") or _attribute(
        span.get("attributes") or {}, "openinference.span.kind"
    )
    return str(value).upper() if value else None


def _parse_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


@dataclass(eq=False)
class DeepSeekHarnessAgent(AgentRunner):
    binding: AgentBinding | None = None
    model: str = _DEFAULT_MODEL
    api_base: str | None = None
    api_key: str | None = None
    dsh_command: list[str] = field(default_factory=_resolve_dsh_command)
    profile: str = field(default_factory=lambda: os.environ.get("A2E_DEEPSEEK_PROFILE", "headless"))
    run_deadline: float = _RUN_DEADLINE
    name: str = field(init=False)

    def __post_init__(self) -> None:
        if self.binding is None:
            raise ValueError("DeepSeekHarnessAgent requires a binding")
        self.name = f"deepseek-harness-{self.binding.name}"

    @staticmethod
    def _current_traceparent() -> str | None:
        try:
            from opentelemetry import trace as otel_trace

            context = otel_trace.get_current_span().get_span_context()
            if not context.is_valid:
                return None
            return f"00-{context.trace_id:032x}-{context.span_id:016x}-{int(context.trace_flags):02x}"
        except Exception:
            return None

    @staticmethod
    def _current_project_name() -> str | None:
        try:
            from opentelemetry import trace as otel_trace

            resource = getattr(otel_trace.get_current_span(), "resource", None)
            if resource is None:
                return None
            return resource.attributes.get("openinference.project.name")
        except Exception:
            return None

    async def _collect_span_stats(self, traceparent: str | None) -> tuple[int, list[ToolCall]]:
        trace_id = _trace_id_from_traceparent(traceparent)
        if not trace_id:
            return 0, []
        endpoint = os.environ.get(
            "A2E_COLLECTOR_ENDPOINT", "http://127.0.0.1:6006"
        ).rstrip("/")
        project = self._current_project_name() or os.environ.get("A2E_PROJECT_NAME") or "default"
        url = f"{endpoint}/v1/projects/{quote(project, safe='')}/spans?limit=1000"
        headers = {"accept": "application/json"}
        if os.environ.get("A2E_API_KEY"):
            headers["authorization"] = f"Bearer {os.environ['A2E_API_KEY']}"

        mine: list[dict[str, Any]] = []
        stable_signature: tuple[str, ...] | None = None
        stable_polls = 0
        try:
            import httpx

            # Long coding traces can make the project response several
            # megabytes.  A transient timeout must not erase an otherwise
            # complete trajectory summary, so give each read enough time and
            # retry individual polls instead of abandoning the whole query.
            async with httpx.AsyncClient(timeout=30.0) as client:
                for _ in range(15):
                    try:
                        response = await client.get(url, headers=headers)
                        response.raise_for_status()
                        spans = list((response.json() or {}).get("data", []))
                    except Exception:
                        await asyncio.sleep(1)
                        continue
                    mine = [
                        span
                        for span in spans
                        if (span.get("context") or {}).get("trace_id") == trace_id
                    ]
                    signature = tuple(
                        sorted(
                            str(span.get("id") or span.get("span_id") or span.get("name"))
                            for span in mine
                        )
                    )
                    stable_polls = (
                        stable_polls + 1
                        if signature and signature == stable_signature
                        else 0
                    )
                    stable_signature = signature
                    kinds = {_span_kind(span) for span in mine}
                    if "AGENT" in kinds and "LLM" in kinds and stable_polls >= 2:
                        break
                    await asyncio.sleep(1)
        except Exception:
            return 0, []

        tool_calls: list[ToolCall] = []
        for span in mine:
            if _span_kind(span) != "TOOL":
                continue
            attributes = span.get("attributes") or {}
            tool_calls.append(
                ToolCall(
                    name=_attribute(attributes, "tool.name") or span.get("name") or "?",
                    arguments=_parse_json_dict(_attribute(attributes, "input.value")),
                    result=_attribute(attributes, "output.value"),
                    error=(
                        span.get("status_message")
                        if span.get("status_code") == "ERROR"
                        else None
                    ),
                )
            )
        return sum(1 for span in mine if _span_kind(span) == "LLM"), tool_calls

    async def run(self, task: TaskInput) -> TaskTrace:
        start = time.perf_counter()
        traceparent = self._current_traceparent()
        workspace = tempfile.mkdtemp(prefix="a2e-deepseek-")
        patch_path = Path(workspace) / "a2e-runner.patch.yml"
        patch_path.write_text(
            "- id: agent-default-model\n"
            "  config:\n"
            "    provider: deepseek-official\n"
            "    model: !!js process.env.A2E_MODEL\n",
            encoding="utf-8",
        )
        prompt = f"{self.binding.render_system_prompt()}\n\nUser task:\n{task.instruction}"
        args = [
            *self.dsh_command,
            "--profile",
            self.profile,
            "--patch",
            str(patch_path),
            prompt,
        ]
        env = dict(os.environ)
        env["A2E_MODEL"] = self.model
        env["DSH_PERMISSION_MODE"] = "danger-full-access"
        env.setdefault("DSH_TELEMETRY_DISABLED", "1")
        if self.api_key:
            env["DEEPSEEK_API_KEY"] = self.api_key
        if self.api_base:
            env["DEEPSEEK_BASE_URL"] = self.api_base
        collector = os.environ.get("A2E_COLLECTOR_ENDPOINT")
        if collector:
            env["A2E_COLLECTOR_ENDPOINT"] = collector
        project = self._current_project_name() or os.environ.get("A2E_PROJECT_NAME")
        if project:
            env["A2E_PROJECT_NAME"] = project
        if traceparent:
            env["TRACEPARENT"] = traceparent

        try:
            with _BindingBridge(self.binding, task.initial_state, workspace) as config_path:
                env["A2E_DEEPSEEK_BINDING_CONFIG"] = config_path
                process = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=workspace,
                )
                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        process.communicate(), timeout=self.run_deadline
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    return TaskTrace(
                        task_id=task.task_id,
                        agent_name=self.name,
                        status="error",
                        turns=0,
                        elapsed_seconds=time.perf_counter() - start,
                        trace_id=_trace_id_from_traceparent(traceparent),
                        error=f"DeepSeek Harness exceeded {self.run_deadline:.0f}s deadline",
                    )

            stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
            turns, tool_calls = await self._collect_span_stats(traceparent)
            error = stderr or None
            if process.returncode != 0 and not error:
                error = f"DeepSeek Harness exited with code {process.returncode}"
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="ok" if stdout and process.returncode == 0 else "error",
                turns=turns,
                tool_calls=tuple(tool_calls),
                final_answer=stdout or None,
                elapsed_seconds=time.perf_counter() - start,
                trace_id=_trace_id_from_traceparent(traceparent),
                error=error[:1000] if error else None,
            )
        except Exception as exc:
            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="error",
                turns=0,
                elapsed_seconds=time.perf_counter() - start,
                trace_id=_trace_id_from_traceparent(traceparent),
                error=(str(exc) or type(exc).__name__)[:1000],
            )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

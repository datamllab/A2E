"""PiAgent — single-agent runner via the Pi coding agent CLI.

Dataset-agnostic: consumes an ``AgentBinding`` and drives any benchmark by
spawning the Pi CLI as a subprocess. A loopback bridge registers the binding's
tools as native Pi function tools and delegates execution back to Python.

Pi's ``a2e-pi-monitor`` extension (loaded via ``--extension``) captures
AGENT / LLM / TOOL spans and exports them via OTLP to A2E independently.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import shutil
import tempfile
import threading
import time
from collections.abc import Mapping
from contextlib import nullcontext
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ageneval.task.core import AgentBinding, AgentRunner, TaskInput, TaskTrace, ToolCall

_DEFAULT_MODEL = os.environ.get("A2E_MODEL") or "qwen-plus"
_MAX_TURNS = 40
_RUN_DEADLINE = float(os.environ.get("A2E_PI_DEADLINE", "600"))

# Pi's built-in providers read standard env vars for their API key.  When the
# runner passes no explicit provider, guess from whichever key is present so
# a bare ``DEEPSEEK_API_KEY=... uv run ... --agent pi`` just works.
_PROVIDER_BY_KEY = [
    ("OPENAI_API_KEY", "openai"),
    ("DEEPSEEK_API_KEY", "deepseek"),
    ("ANTHROPIC_API_KEY", "anthropic"),
]


class _BindingBridge:
    """Expose an ``AgentBinding`` to Pi over a token-protected loopback API.

    Pi is a Node.js subprocess while A2E bindings are synchronous Python
    callables. A short-lived localhost server is the smallest boundary that
    preserves the existing binding contract, including live sandbox handles.
    """

    def __init__(self, binding: AgentBinding, state: Mapping[str, Any], directory: str) -> None:
        self.binding = binding
        self.state = state
        self.directory = directory
        self.token = secrets.token_urlsafe(32)
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.config_path = Path(directory) / "a2e-pi-binding.json"

    def __enter__(self) -> str:
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if self.path != "/tool" or self.headers.get("authorization") != f"Bearer {bridge.token}":
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
                    payload = json.dumps({"result": result}, ensure_ascii=False, default=str).encode()
                    self.send_response(200)
                    self.send_header("content-type", "application/json; charset=utf-8")
                    self.send_header("content-length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except Exception as exc:
                    payload = json.dumps({"error": str(exc) or type(exc).__name__}).encode()
                    self.send_response(500)
                    self.send_header("content-type", "application/json")
                    self.send_header("content-length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)

            def log_message(self, _format: str, *_args: Any) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        port = self.server.server_address[1]
        config = {
            "endpoint": f"http://127.0.0.1:{port}/tool",
            "token": self.token,
            "systemPrompt": (
                f"{self.binding.render_system_prompt()}\n\n"
                "The tools above are registered as native function tools. Invoke them with "
                "tool calls; do not print an action JSON object instead of calling a tool."
            ),
            "tools": _binding_tool_definitions(self.binding),
        }
        self.config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        return str(self.config_path)

    def __exit__(self, *_exc_info: object) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=2)


def _binding_tool_definitions(binding: AgentBinding) -> list[dict[str, Any]]:
    """Convert A2E's OpenAI-style schemas to the Pi extension config."""
    definitions: list[dict[str, Any]] = []
    for schema in binding.tool_schemas:
        function = schema.get("function", schema)
        if not isinstance(function, Mapping) or not function.get("name"):
            continue
        definitions.append(
            {
                "name": str(function["name"]),
                "description": str(function.get("description", "")),
                "parameters": dict(function.get("parameters") or {"type": "object", "properties": {}}),
            }
        )
    return definitions


def _trace_id_from_traceparent(traceparent: str | None) -> str | None:
    if not traceparent:
        return None
    parts = traceparent.split("-")
    return parts[1] if len(parts) == 4 and len(parts[1]) == 32 else None


def _default_provider() -> str:
    explicit = os.environ.get("PI_PROVIDER")
    if explicit:
        return explicit
    for key, provider in _PROVIDER_BY_KEY:
        if os.environ.get(key):
            return provider
    return "openai"


def _repo_root() -> Path:
    """Return the repository root (nearest ancestor holding ``.git``)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    # Fallback: walk up until we find the monitor/ directory.
    for parent in here.parents:
        if (parent / "monitor").is_dir():
            return parent
    return here.parents[0]


def _resolve_pi_cli() -> str:
    """Return the Pi CLI command to execute.

    Checks, in order:
    1. ``A2E_PI_CLI`` env var (absolute path or full command).
    2. ``pi`` on PATH.
    3. Falls back to the vendored CLI under the a2e-pi-monitor node_modules.
    """
    custom = os.environ.get("A2E_PI_CLI")
    if custom:
        return custom  # may be "pi" or "node /abs/path/cli.js"

    if shutil.which("pi"):
        return "pi"

    # Vendored fallback: relative to the monitor package
    monitor_root = _repo_root() / "monitor" / "instrumentation-js" / "a2e-pi-monitor"
    cli_js = monitor_root / "node_modules" / "@earendil-works" / "pi-coding-agent" / "dist" / "cli.js"
    if cli_js.is_file():
        return f"node {cli_js}"

    raise RuntimeError(
        "Pi CLI not found. Set A2E_PI_CLI to the pi binary path, "
        "install pi globally (npm install -g @earendil-works/pi-coding-agent), "
        "or ensure the a2e-pi-monitor devDependencies are installed."
    )


def _resolve_monitor_extension() -> str | None:
    """Return the absolute path to the a2e-pi-monitor package directory.

    Required so Pi loads the monitor extension and exports traces to A2E.
    """
    custom = os.environ.get("A2E_PI_MONITOR")
    if custom:
        return custom

    monitor_root = _repo_root() / "monitor" / "instrumentation-js" / "a2e-pi-monitor"
    if monitor_root.is_dir():
        return str(monitor_root)

    return None


@dataclass(eq=False)
class PiAgent(AgentRunner):
    """Single-agent runner that delegates to the Pi coding agent CLI.

    Pi is a Node.js agent harness.  This runner spawns ``pi`` (or a vendored
    CLI) as a subprocess and captures its stdout as the final answer.  Pi's
    own ``a2e-pi-monitor`` extension handles OTel trace export — no Python
    instrumentor is needed (``framework="none"``).
    """

    binding: AgentBinding | None = None
    model: str = _DEFAULT_MODEL
    provider: str = field(default_factory=_default_provider)
    api_base: str | None = None
    api_key: str | None = None
    max_turns: int = _MAX_TURNS
    pi_cli: str = field(default_factory=_resolve_pi_cli)
    monitor_extension: str | None = field(default_factory=_resolve_monitor_extension)
    run_deadline: float = _RUN_DEADLINE
    name: str = field(init=False)

    def __post_init__(self) -> None:
        if self.binding is None:
            raise ValueError("PiAgent requires a binding")
        self.name = f"pi-{self.binding.name}"

    @staticmethod
    def _current_traceparent() -> str | None:
        """Return the W3C ``traceparent`` for the current OTel span, if any.

        The ExperimentRunner runs each task inside a Python OTel root span.
        Serializing its trace/span ids into the ``TRACEPARENT`` env var lets
        Pi's Node.js exporter create spans as children of that same trace.
        """
        try:
            from opentelemetry import trace as otel_trace

            ctx = otel_trace.get_current_span().get_span_context()
            if not ctx.is_valid:
                return None
            return (
                f"00-{ctx.trace_id:032x}-{ctx.span_id:016x}-{int(ctx.trace_flags):02x}"
            )
        except Exception:
            return None

    @staticmethod
    def _current_project_name() -> str | None:
        """Return the A2E project name from the current OTel span's resource.

        The a2e-client wraps each task in a CHAIN span whose resource carries
        ``openinference.project.name`` (the experiment's ``Experiment-<id>``
        project). Pi's monitor must export to that same project or the UI's
        trace viewer (which queries by the experiment project) finds nothing.
        """
        try:
            from opentelemetry import trace as otel_trace

            resource = getattr(otel_trace.get_current_span(), "resource", None)
            if resource is None:
                return None
            return resource.attributes.get("openinference.project.name")
        except Exception:
            return None

    async def _collect_span_stats(self, traceparent: str | None) -> tuple[int, list[ToolCall]]:
        """Return ``(turns, tool_calls)`` by reading Pi's spans back from A2E.

        Pi's ``a2e-pi-monitor`` extension already exports AGENT / LLM / TOOL
        spans to A2E. Rather than duplicating that bookkeeping in the Python
        runner, query the spans API for this trace and count LLM spans as
        ``turns`` and TOOL spans as ``tool_calls``.
        """
        trace_id = _trace_id_from_traceparent(traceparent)
        if not trace_id:
            return 0, []

        endpoint = os.environ.get("A2E_COLLECTOR_ENDPOINT", "http://127.0.0.1:6006").rstrip("/")
        project = self._current_project_name() or os.environ.get("A2E_PROJECT_NAME") or "default"
        url = f"{endpoint}/v1/projects/{quote(project, safe='')}/spans?limit=1000"
        headers = {"accept": "application/json"}
        if os.environ.get("A2E_API_KEY"):
            headers["authorization"] = f"Bearer {os.environ['A2E_API_KEY']}"

        # The collector may expose the root AGENT span before its LLM/TOOL
        # children. Wait for a complete, stable set instead of stopping on the
        # first span, which was the source of truncated trajectories in the UI.
        spans: list[dict[str, Any]] = []
        stable_signature: tuple[str, ...] | None = None
        stable_polls = 0
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                for _ in range(15):
                    resp = await client.get(url, headers=headers)
                    resp.raise_for_status()
                    spans = list((resp.json() or {}).get("data", []))
                    mine = [s for s in spans if (s.get("context") or {}).get("trace_id") == trace_id]
                    signature = tuple(sorted(str(s.get("id") or s.get("span_id") or s.get("name")) for s in mine))
                    kinds = {_span_kind(s) for s in mine}
                    stable_polls = stable_polls + 1 if signature and signature == stable_signature else 0
                    stable_signature = signature
                    if "AGENT" in kinds and "LLM" in kinds and stable_polls >= 2:
                        break
                    await asyncio.sleep(1.0)
        except Exception:
            return 0, []

        mine = [s for s in spans if (s.get("context") or {}).get("trace_id") == trace_id]
        llm_count = sum(1 for s in mine if _span_kind(s) == "LLM")
        tool_calls: list[ToolCall] = []
        for s in mine:
            if _span_kind(s) != "TOOL":
                continue
            attrs = s.get("attributes") or {}
            tool_calls.append(
                ToolCall(
                    name=_attribute(attrs, "tool.name") or s.get("name") or "?",
                    arguments=_parse_json_dict(_attribute(attrs, "input.value")),
                    result=_attribute(attrs, "output.value"),
                    error=s.get("status_message") if s.get("status_code") == "ERROR" else None,
                )
            )
        return llm_count, tool_calls

    async def run(self, task: TaskInput) -> TaskTrace:
        start = time.perf_counter()

        # ---- trace context (W3C traceparent) --------------------------------
        # The ExperimentRunner wraps this run in a Python OTel root span.  Pass
        # its trace context to Pi so Pi's AGENT/LLM/TOOL spans become children
        # of the same trace — the UI then shows one combined span tree.
        traceparent = self._current_traceparent()

        # ---- build CLI args --------------------------------------------------
        args: list[str] = []
        pi_cmd = self.pi_cli
        if " " in pi_cmd:
            args.extend(pi_cmd.split())
        else:
            args.append(pi_cmd)

        args += [
            "--provider", self.provider,
            "--model", self.model,
            "--print",
            "--no-session",
            "--thinking", "off",
            "--no-context-files",
        ]

        if self.monitor_extension:
            args += ["--extension", self.monitor_extension]

        tool_definitions = _binding_tool_definitions(self.binding)
        if tool_definitions:
            # Benchmark tools come from the binding extension. Disable host
            # coding tools, especially when the real filesystem is in Docker.
            args.append("--no-builtin-tools")
        else:
            args.append("--no-tools")
        args.append(task.instruction)

        # ---- build env -------------------------------------------------------
        env = dict(os.environ)

        # Provider API key: Pi's built-in providers read standard env vars
        # (OPENAI_API_KEY, DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, etc.).
        # The user sets these in .env; pass them through unchanged.  If the
        # runner passed an explicit ``api_key``, map it to the provider's key.
        if self.api_key:
            provider_key = {
                "openai": "OPENAI_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
            }.get(self.provider, "OPENAI_API_KEY")
            env[provider_key] = self.api_key

        # A2E collector — where Pi's OTel exporter sends traces
        collector = os.environ.get("A2E_COLLECTOR_ENDPOINT")
        if collector:
            env["A2E_COLLECTOR_ENDPOINT"] = collector
        # Pi must export to the experiment's project (Experiment-<id>), not the
        # default, or the UI trace viewer won't find its spans. Prefer the
        # current span's resource project name, then the env var.
        project = self._current_project_name() or os.environ.get("A2E_PROJECT_NAME")
        if project:
            env["A2E_PROJECT_NAME"] = project

        # Pi startup flags to skip network checks
        env.setdefault("PI_OFFLINE", "true")
        env.setdefault("PI_SKIP_VERSION_CHECK", "true")

        # W3C trace context: makes Pi's spans children of the Python root span
        if traceparent:
            env["TRACEPARENT"] = traceparent

        # The temporary cwd only holds Pi runtime files. Benchmark tools act
        # on task.initial_state (including a live Docker sandbox) via the
        # loopback bridge, so nothing is copied between host and container.
        workspace = tempfile.mkdtemp(prefix="a2e-pi-")
        bridge = (
            _BindingBridge(self.binding, task.initial_state, workspace)
            if tool_definitions
            else nullcontext(None)
        )

        # ---- execute ---------------------------------------------------------
        try:
            with bridge as binding_config:
                if binding_config:
                    env["A2E_PI_BINDING_CONFIG"] = binding_config
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=workspace,
                )
                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=self.run_deadline,
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    return TaskTrace(
                        task_id=task.task_id,
                        agent_name=self.name,
                        status="error",
                        turns=0,
                        elapsed_seconds=time.perf_counter() - start,
                        trace_id=_trace_id_from_traceparent(traceparent),
                        error=f"Pi exceeded {self.run_deadline:.0f}s deadline",
                    )

            stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
            elapsed = time.perf_counter() - start

            # ---- parse output -------------------------------------------------
            final_answer = stdout or None
            error = stderr or None
            if proc.returncode != 0 and not final_answer:
                error = error or f"Pi exited with code {proc.returncode}"

            # Pi's spans land in A2E asynchronously; poll briefly so the
            # LLM/TOOL counts reflect the whole run rather than a partial batch.
            turns, tool_calls = await self._collect_span_stats(traceparent)

            return TaskTrace(
                task_id=task.task_id,
                agent_name=self.name,
                status="ok" if final_answer and proc.returncode == 0 else "error",
                turns=turns,
                tool_calls=tuple(tool_calls),
                final_answer=final_answer,
                elapsed_seconds=elapsed,
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


def _parse_json_dict(value: Any) -> dict[str, Any]:
    """Parse a JSON string into a dict; fall back to an empty dict otherwise.

    Pi records tool arguments as a JSON string in ``input.value``. ``ToolCall``
    expects a mapping, so best-effort decode it (non-object/parse failures → ``{}``).
    """
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        import json

        parsed = json.loads(value)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _attribute(attributes: Mapping[str, Any], name: str) -> Any:
    """Read either a flattened OTel key or the server's nested JSON form."""
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

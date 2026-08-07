"""OpenTelemetry / OpenInference setup helpers.

Wire any A2E agent run to the a2e OTLP receiver in one call.

Inspired by the ``a2e_setup.py`` pattern used in upstream A2E
tau-bench examples, but fully self-contained: every import resolves
inside A2E — no path-based external dependency.
"""

from __future__ import annotations

import importlib
import os
from typing import Iterable, Literal

from opentelemetry import trace as trace_api
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

Framework = Literal[
    "none", "langchain", "claude_agent_sdk", "anthropic", "smolagents", "openai_agents",
    "autogen_agentchat", "crewai", "llama_index", "google_adk", "agno",
]

# framework -> (module path, Instrumentor class name). 不在模块层 import。
_INSTRUMENTOR_REGISTRY: dict[str, tuple[str, str]] = {
    "langchain":         ("openinference.instrumentation.langchain",         "LangChainInstrumentor"),
    "claude_agent_sdk":  ("openinference.instrumentation.claude_agent_sdk",  "ClaudeAgentSDKInstrumentor"),
    "anthropic":         ("openinference.instrumentation.anthropic",         "AnthropicInstrumentor"),
    "smolagents":        ("openinference.instrumentation.smolagents",        "SmolagentsInstrumentor"),
    "openai_agents":     ("openinference.instrumentation.openai_agents",     "OpenAIAgentsInstrumentor"),
    "autogen_agentchat": ("openinference.instrumentation.autogen_agentchat", "AutogenAgentChatInstrumentor"),
    "crewai":            ("openinference.instrumentation.crewai",            "CrewAIInstrumentor"),
    "llama_index":       ("openinference.instrumentation.llama_index",       "LlamaIndexInstrumentor"),
    "google_adk":        ("openinference.instrumentation.google_adk",        "GoogleADKInstrumentor"),
    "agno":              ("openinference.instrumentation.agno",              "AgnoInstrumentor"),
}


def setup_instrumentation(
    *,
    project_name: str = "a2e-default",
    endpoint: str | None = None,
    framework: Framework = "none",
    batch: bool = False,
    extra_resource_attributes: Iterable[tuple[str, str]] = (),
) -> TracerProvider:
    """Build a TracerProvider, register an OTLP exporter, and install the
    relevant openinference instrumentor.

    Args:
        project_name: A2E "project" the spans land in.
        endpoint: OTLP HTTP traces endpoint. Falls back to env
            ``A2E_COLLECTOR_ENDPOINT`` or ``http://127.0.0.1:6006``.
        framework: which openinference instrumentor to install.
        batch: ``True`` uses ``BatchSpanProcessor`` (production), ``False``
            uses ``SimpleSpanProcessor`` (deterministic for smoke tests).
        extra_resource_attributes: extra ``(key, value)`` pairs to merge into
            the OTel ``Resource`` (e.g. agent name, dataset name, run id).

    Returns:
        The configured ``TracerProvider`` (already set as global).
    """
    endpoint = endpoint or os.environ.get(
        "A2E_COLLECTOR_ENDPOINT", "http://127.0.0.1:6006"
    )
    traces_url = endpoint.rstrip("/") + "/v1/traces"

    resource_attrs: dict[str, str] = {
        "openinference.project.name": project_name,
        "service.name": project_name,
    }
    for k, v in extra_resource_attributes:
        resource_attrs[k] = v
    resource = Resource.create(resource_attrs)

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=traces_url)
    processor_cls = BatchSpanProcessor if batch else SimpleSpanProcessor
    provider.add_span_processor(processor_cls(exporter))

    trace_api.set_tracer_provider(provider)

    _install_instrumentor(framework, provider)
    return provider


def _install_instrumentor(framework: Framework, provider: TracerProvider) -> None:
    if framework == "none":
        return
    entry = _INSTRUMENTOR_REGISTRY.get(framework)
    if entry is None:
        raise ValueError(
            f"Unknown framework: {framework!r}. Known: {['none', *_INSTRUMENTOR_REGISTRY]}"
        )
    module_path, class_name = entry
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise RuntimeError(
            f"Instrumentor for {framework!r} not importable ({module_path}); "
            "the vendored monitor package may be missing from the workspace."
        ) from exc
    getattr(module, class_name)().instrument(tracer_provider=provider)


def shutdown(provider: TracerProvider) -> None:
    """Flush pending spans and shut down the provider."""
    provider.force_flush(timeout_millis=10_000)
    provider.shutdown()

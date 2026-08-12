# The following line is needed to ensure that other modules using the
# `a2e.*` path can be discovered by Bazel. For details,
# see: https://github.com/a2e-ai/openinference/issues/398
# IMPORTANT: This must come before any imports that depend on namespace packages
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

import sys
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing import Any, Optional

from .session.session import (
    NotebookEnvironment,
    Session,
    active_session,
    close_app,
    delete_all,
    launch_app,
)
from .trace.fixtures import load_example_traces
from .trace.trace_dataset import TraceDataset
from .version import __version__

# module level doc-string
__doc__ = """
a2e-server - AI Observability Platform
=====================================================================
**a2e** is a Python package that provides AI observability and
tracing built on OpenTelemetry.
"""

__all__ = [
    "__version__",
    "active_session",
    "close_app",
    "launch_app",
    "delete_all",
    "Session",
    "load_example_traces",
    "TraceDataset",
    "NotebookEnvironment",
    "evals",
]


class A2EClientFinder(MetaPathFinder):
    def find_spec(self, fullname: Any, path: Any, target: Any = None) -> Optional[ModuleSpec]:
        if fullname == "a2e.session.client":
            return ModuleSpec(fullname, A2EClientLoader())
        return None


class A2EClientLoader(Loader):
    def create_module(self, spec: ModuleSpec) -> None:
        return None

    def exec_module(self, module: ModuleType) -> None:
        raise ImportError(
            "The legacy `a2e.session.client.Client` class has been removed.\n"
            "Please use the `a2e-client` package instead:\n\n"
            "pip install a2e-client\n\n"
            "```python\n"
            "from a2e.client import Client\n"
            "```\n"
        )


class A2ETraceFinder(MetaPathFinder):
    def find_spec(self, fullname: Any, path: Any, target: Any = None) -> Optional[ModuleSpec]:
        if fullname == "a2e.trace.openai":
            return ModuleSpec(fullname, A2ETraceOpenAILoader())
        if fullname == "a2e.trace.langchain":
            return ModuleSpec(fullname, A2ETraceLangchainLoader())
        if fullname == "a2e.trace.llama_index":
            return ModuleSpec(fullname, A2ETraceLlamaIndexLoader())
        return None


class A2ETraceOpenAILoader(Loader):
    def create_module(self, spec: ModuleSpec) -> None:
        return None

    def exec_module(self, module: ModuleType) -> None:
        raise ImportError(
            "The legacy `a2e.trace.openai` instrumentor module has been removed.\n"
            "Please use OpenInference to instrument the OpenAI SDK. Additionally, the "
            "`a2e.otel` module can be used to quickly configure OpenTelemetry:\n\n"
            "https://example.com/docs/a2e/tracing/integrations-tracing/openai"
            "\n\n"
            "Example usage:\n\n"
            "pip install openinference-instrumentation-openai\n\n"
            "```python\n"
            "from a2e.otel import register\n"
            "from openinference.instrumentation.openai import OpenAIInstrumentor\n\n"
            "tracer_provider = register()\n"
            "OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)\n"
            "```\n"
        )


class A2ETraceLangchainLoader(Loader):
    def create_module(self, spec: ModuleSpec) -> None:
        return None

    "Please use OpenInference to instrument the Langchain SDK. Additionally, the `a2e.otel` "
    "module can be used to quickly configure OpenTelemetry:\n\n"

    def exec_module(self, module: ModuleType) -> None:
        raise ImportError(
            "The legacy `a2e.trace.langchain` instrumentor module has been removed.\n"
            "Please use OpenInference to instrument the LangChain SDK. Additionally, the "
            "`a2e.otel` module can be used to quickly configure OpenTelemetry:\n\n"
            "https://example.com/docs/a2e/tracing/integrations-tracing/langchain"
            "\n\n"
            "Example usage:\n\n"
            "```python\n"
            "from a2e.otel import register\n"
            "from openinference.instrumentation.langchain import LangChainInstrumentor\n\n"
            "tracer_provider = register()\n"
            "LangChainInstrumentor().instrument(tracer_provider=tracer_provider)\n"
            "```\n"
        )


class A2ETraceLlamaIndexLoader(Loader):
    def create_module(self, spec: ModuleSpec) -> None:
        return None

    def exec_module(self, module: ModuleType) -> None:
        raise ImportError(
            "The legacy `a2e.trace.llama_index` instrumentor module has been removed.\n"
            "Please use OpenInference to instrument the LlamaIndex SDK. Additionally, the "
            "`a2e.otel` module can be used to quickly configure OpenTelemetry:\n\n"
            "https://example.com/docs/a2e/tracing/integrations-tracing/llamaindex"
            "\n\n"
            "Example usage:\n\n"
            "```python\n"
            "from a2e.otel import register\n"
            "from openinference.instrumentation.llama_index import LlamaIndexInstrumentor\n\n"
            "tracer_provider = register()\n"
            "LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)\n"
            "```\n"
        )


sys.meta_path.append(A2EClientFinder())
sys.meta_path.append(A2ETraceFinder())

"""Single example: trace Claude Agent SDK and print captured span attributes.

Requirements:
  - Set ANTHROPIC_API_KEY
  - (Optional) A2E_COLLECTOR_ENDPOINT for A2E Cloud
    Default: http://127.0.0.1:6006/v1/traces (local A2E)
"""

import asyncio
import json
import os
import pathlib
import sys
from typing import Any, Optional

_MONITOR_ROOT = pathlib.Path(__file__).resolve().parents[3]
for _src in (
    _MONITOR_ROOT / "instrumentation/openinference-instrumentation-claude-agent-sdk/src",
    _MONITOR_ROOT / "openinference-instrumentation/src",
    _MONITOR_ROOT / "openinference-semantic-conventions/src",
):
    sys.path.insert(0, str(_src))

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from openinference.instrumentation.claude_agent_sdk import ClaudeAgentSDKInstrumentor

A2E_ENDPOINT = os.environ.get("A2E_COLLECTOR_ENDPOINT", "http://127.0.0.1:6006/v1/traces")

_TASK_PROMPT = (
    "Use the Task tool to delegate a sub-agent. The sub-agent must use the Bash tool "
    "to run: `printf 'hello' | wc -c`. Return exactly the numeric output and nothing else."
)


def _format_trace_id(trace_id: int) -> str:
    return f"{trace_id:032x}"


def _format_span_id(span_id: int) -> str:
    return f"{span_id:016x}"


def _format_parent_span_id(span: Any) -> Optional[str]:
    if span.parent is None:
        return None
    return _format_span_id(span.parent.span_id)


def _span_to_dict(span: Any) -> dict[str, Any]:
    context = span.context
    instrumentation_scope = getattr(span, "instrumentation_scope", None)
    resource = getattr(span, "resource", None)
    status = getattr(span, "status", None)

    return {
        "name": span.name,
        "context": {
            "trace_id": _format_trace_id(context.trace_id),
            "span_id": _format_span_id(context.span_id),
            "trace_flags": str(context.trace_flags),
            "trace_state": str(context.trace_state),
            "is_remote": context.is_remote,
        },
        "parent_span_id": _format_parent_span_id(span),
        "kind": str(span.kind),
        "start_time": span.start_time,
        "end_time": span.end_time,
        "status": {
            "status_code": str(status.status_code) if status is not None else None,
            "description": status.description if status is not None else None,
        },
        "attributes": dict(span.attributes or {}),
        "events": [
            {
                "name": event.name,
                "timestamp": event.timestamp,
                "attributes": dict(event.attributes or {}),
            }
            for event in span.events
        ],
        "links": [
            {
                "context": {
                    "trace_id": _format_trace_id(link.context.trace_id),
                    "span_id": _format_span_id(link.context.span_id),
                    "trace_flags": str(link.context.trace_flags),
                    "trace_state": str(link.context.trace_state),
                    "is_remote": link.context.is_remote,
                },
                "attributes": dict(link.attributes or {}),
            }
            for link in span.links
        ],
        "resource": dict(resource.attributes or {}) if resource is not None else {},
        "instrumentation_scope": {
            "name": instrumentation_scope.name,
            "version": instrumentation_scope.version,
            "schema_url": instrumentation_scope.schema_url,
            "attributes": dict(instrumentation_scope.attributes or {}),
        }
        if instrumentation_scope is not None
        else None,
    }


def _print_trace_tree(spans: tuple[Any, ...]) -> None:
    spans_by_id = {span.context.span_id: span for span in spans}
    children_by_parent_id: dict[Optional[int], list[Any]] = {}
    for span in spans:
        parent_id = span.parent.span_id if span.parent is not None else None
        if parent_id not in spans_by_id:
            parent_id = None
        children_by_parent_id.setdefault(parent_id, []).append(span)

    def print_span(span: Any, depth: int) -> None:
        context = span.context
        parent_span_id = _format_parent_span_id(span)
        prefix = "  " * depth
        print(
            f"{prefix}- {span.name} "
            f"span_id={_format_span_id(context.span_id)} "
            f"parent_span_id={parent_span_id}"
        )
        for child in children_by_parent_id.get(context.span_id, []):
            print_span(child, depth + 1)

    print("\nOTel span tree:")
    for root_span in children_by_parent_id.get(None, []):
        print_span(root_span, 0)


def _setup_tracing() -> tuple[trace_sdk.TracerProvider, InMemorySpanExporter]:
    tracer_provider = trace_sdk.TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(A2E_ENDPOINT)))
    memory_exporter = InMemorySpanExporter()
    tracer_provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
    ClaudeAgentSDKInstrumentor().instrument(tracer_provider=tracer_provider)
    return tracer_provider, memory_exporter


async def main() -> None:
    tracer_provider, memory_exporter = _setup_tracing()

    # Import after instrument() so the traced query is used.
    from claude_agent_sdk import ClaudeAgentOptions, query  # noqa: E402

    options = ClaudeAgentOptions(
        allowed_tools=["Bash", "Task", "TaskOutput"],
        permission_mode="bypassPermissions",
    )

    result: Optional[str] = None
    async for message in query(prompt=_TASK_PROMPT, options=options):
        if getattr(message, "result", None) is not None:
            result = message.result

    print(f"Result: {result!r}")

    tracer_provider.force_flush()
    spans = memory_exporter.get_finished_spans()
    _print_trace_tree(spans)

    print("\nCaptured OTel spans:")
    for span in spans:
        print(f"- {span.name}")
        print(json.dumps(_span_to_dict(span), indent=2, sort_keys=True, default=str))

    all_spans = [json.loads(span.to_json()) for span in spans]
    with open("spans.json", "w") as f:
        json.dump(all_spans, f, indent=2, default=str)
    print(f"\n{len(all_spans)} spans saved to spans.json")

    print("\nDone. View traces in A2E Cloud or at http://127.0.0.1:6006 (local).")


if __name__ == "__main__":
    asyncio.run(main())

"""Offline verification that agno's skill-access tools surface as SKILL spans.

agno's ``Skills.get_tools()`` injects three Function tools
(``get_skill_instructions`` / ``get_skill_reference`` / ``get_skill_script``).
They all run through ``FunctionCall.execute()``, which the AgnoInstrumentor
wraps. This script drives those tools directly (no LLM / API key needed) and
asserts each one produces a ``SKILL`` span with ``skill.*`` attributes.

Run with the only venv that has agno installed:

    task/.venv/bin/python monitor/runs/agno_skill_trace.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

_MONITOR_ROOT = pathlib.Path(__file__).resolve().parents[1]
for _src in (
    _MONITOR_ROOT / "instrumentation/openinference-instrumentation-agno/src",
    _MONITOR_ROOT / "openinference-instrumentation/src",
    _MONITOR_ROOT / "openinference-semantic-conventions/src",
):
    sys.path.insert(0, str(_src))

from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agno.skills import LocalSkills, Skills
from agno.tools.function import FunctionCall

from openinference.instrumentation.agno import AgnoInstrumentor

SKILL_NAME = "demo-skill"
REFERENCE_FILE = "guide.md"
SCRIPT_FILE = "hello.py"

SKILL_MD = """\
---
name: demo-skill
description: A demo skill used to verify that agno skill tools emit SKILL spans.
---

# Demo Skill

Use this skill whenever you need to demonstrate skill monitoring.
"""


def _build_skill_dir(root: pathlib.Path) -> pathlib.Path:
    skill_dir = root / SKILL_NAME
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(SKILL_MD)
    (skill_dir / "references" / REFERENCE_FILE).write_text("# Guide\n\nReference body.\n")
    (skill_dir / "scripts" / SCRIPT_FILE).write_text("print('hello from skill script')\n")
    return skill_dir


def main() -> int:
    exporter = InMemorySpanExporter()
    tracer_provider = trace_sdk.TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    AgnoInstrumentor().instrument(tracer_provider=tracer_provider)

    with tempfile.TemporaryDirectory() as tmp:
        _build_skill_dir(pathlib.Path(tmp))
        skills = Skills(loaders=[LocalSkills(path=str(pathlib.Path(tmp) / SKILL_NAME))])
        tools_by_name = {fn.name: fn for fn in skills.get_tools()}

        invocations = {
            "get_skill_instructions": {"skill_name": SKILL_NAME},
            "get_skill_reference": {"skill_name": SKILL_NAME, "reference_path": REFERENCE_FILE},
            "get_skill_script": {"skill_name": SKILL_NAME, "script_path": SCRIPT_FILE},
        }
        for tool_name, arguments in invocations.items():
            call = FunctionCall(function=tools_by_name[tool_name], arguments=arguments)
            call.execute()

    spans = {s.name: s for s in exporter.get_finished_spans()}

    expected_source = {
        "get_skill_instructions": "agno_skill:instructions",
        "get_skill_reference": "agno_skill:reference",
        "get_skill_script": "agno_skill:script",
    }

    ok = True
    for tool_name, source in expected_source.items():
        span = spans.get(tool_name)
        attrs = dict(span.attributes) if span is not None else {}
        checks = {
            "span exists": span is not None,
            "kind == SKILL": attrs.get("openinference.span.kind") == "SKILL",
            "skill.name": attrs.get("skill.name") == SKILL_NAME,
            "skill.source": attrs.get("skill.source") == source,
            "skill.input.value": bool(attrs.get("skill.input.value")),
            "skill.output.value": bool(attrs.get("skill.output.value")),
        }
        status = "PASS" if all(checks.values()) else "FAIL"
        ok = ok and all(checks.values())
        print(f"[{status}] {tool_name}")
        for label, passed in checks.items():
            print(f"        {'ok ' if passed else 'XX '} {label}")
        if span is not None:
            print(f"        skill.input.value  = {attrs.get('skill.input.value')}")
            out = str(attrs.get("skill.output.value"))
            print(f"        skill.output.value = {out[:120]}{'…' if len(out) > 120 else ''}")

    print("\nall finished spans:")
    print(json.dumps([s.name for s in exporter.get_finished_spans()], indent=2))

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

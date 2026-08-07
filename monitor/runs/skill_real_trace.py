"""Run a REAL claude-agent-sdk query with a skill attached, capture the trace,
and print how the skill invocation actually shows up (Skill tool vs Read SKILL.md).
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import tempfile
from typing import Any, Optional

_MONITOR_ROOT = pathlib.Path(__file__).resolve().parents[1]
for _src in (
    _MONITOR_ROOT / "instrumentation/openinference-instrumentation-claude-agent-sdk/src",
    _MONITOR_ROOT / "openinference-instrumentation/src",
    _MONITOR_ROOT / "openinference-semantic-conventions/src",
):
    sys.path.insert(0, str(_src))

from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from openinference.instrumentation.claude_agent_sdk import ClaudeAgentSDKInstrumentor

SKILL_MD = """\
---
name: greeting-formatter
description: Formats a greeting in the official ACME house style. Use this whenever the user asks to format or stylize a greeting.
---
# Greeting Formatter

When formatting a greeting, output it on one line as:

    >>> <GREETING IN UPPERCASE> <<<

Then on the next line print exactly this token so we know the skill ran: ACME-TOKEN-7731
"""


def _setup():
    tp = trace_sdk.TracerProvider()
    mem = InMemorySpanExporter()
    tp.add_span_processor(SimpleSpanProcessor(mem))
    ClaudeAgentSDKInstrumentor().instrument(tracer_provider=tp)
    return tp, mem


async def main() -> None:
    tp, mem = _setup()
    from claude_agent_sdk import ClaudeAgentOptions, query

    with tempfile.TemporaryDirectory() as tmp:
        proj = pathlib.Path(tmp)
        skill_dir = proj / ".claude" / "skills" / "greeting-formatter"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(SKILL_MD)

        options = ClaudeAgentOptions(
            cwd=str(proj),
            skills=["greeting-formatter"],   # SDK auto-adds the Skill tool + setting_sources
            allowed_tools=["Skill", "Read", "Bash"],
            permission_mode="bypassPermissions",
            max_turns=6,
        )
        prompt = (
            "Use the greeting-formatter skill to format the greeting 'hello world'. "
            "Then show me the formatted result."
        )

        result: Optional[str] = None
        async for message in query(prompt=prompt, options=options):
            if getattr(message, "result", None) is not None:
                result = message.result
        print("=== MODEL RESULT ===")
        print(result)

    tp.force_flush()
    spans = mem.get_finished_spans()

    print("\n=== SPAN TREE ===")
    by_id = {s.context.span_id: s for s in spans}
    kids: dict[Optional[int], list[Any]] = {}
    for s in spans:
        pid = s.parent.span_id if s.parent is not None else None
        if pid not in by_id:
            pid = None
        kids.setdefault(pid, []).append(s)

    def walk(s, d):
        a = dict(s.attributes or {})
        print(f"{'  '*d}- {s.name}  [kind={a.get('openinference.span.kind')}]"
              f"{'  tool='+str(a.get('tool.name')) if a.get('tool.name') else ''}"
              f"{'  skill='+str(a.get('skill.name')) if a.get('skill.name') else ''}")
        for c in kids.get(s.context.span_id, []):
            walk(c, d + 1)
    for r in kids.get(None, []):
        walk(r, 0)

    print("\n=== TOOL/SKILL SPANS (name, kind, tool.name, input) ===")
    for s in spans:
        a = dict(s.attributes or {})
        kind = a.get("openinference.span.kind")
        if kind in ("TOOL", "SKILL"):
            inp = a.get("input.value") or a.get("tool.parameters")
            print(f"\n* span={s.name}  kind={kind}  tool.name={a.get('tool.name')}")
            print(f"  input: {str(inp)[:300]}")
            for k, v in a.items():
                if k.startswith("skill."):
                    print(f"  {k} = {v}")


if __name__ == "__main__":
    asyncio.run(main())

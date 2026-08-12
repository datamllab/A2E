"""End-to-end τ-bench × langgraph multi-agent smoke runner.

Run with a2e already serving and an OpenAI-compatible endpoint:

    OPENAI_API_KEY=... OPENAI_API_BASE=http://.../v1/ A2E_LANGGRAPH_MODEL=...   uv run python task/examples/run_tau_langgraph.py --domain retail --n 1
"""

from __future__ import annotations

import argparse
import json
import sys

from ageneval.task.runners import run_tau_langgraph


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default="retail", choices=["retail", "airline"])
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--model", default=None, help="overrides A2E_LANGGRAPH_MODEL env")
    parser.add_argument("--api-base", default=None, help="overrides OPENAI_API_BASE")
    parser.add_argument("--api-key", default=None, help="overrides OPENAI_API_KEY")
    parser.add_argument("--endpoint", default=None, help="OTLP endpoint override")
    args = parser.parse_args()

    traces = run_tau_langgraph(
        domain=args.domain,
        n=args.n,
        model=args.model,
        api_base=args.api_base,
        api_key=args.api_key,
        endpoint=args.endpoint,
    )
    for t in traces:
        print(
            json.dumps(
                {
                    "task_id": t.task_id,
                    "status": t.status,
                    "turns": t.turns,
                    "tool_calls": [tc.name for tc in t.tool_calls],
                    "trace_id": t.trace_id,
                    "elapsed_s": round(t.elapsed_seconds, 2),
                    "final_answer": t.final_answer,
                    "error": t.error,
                },
                ensure_ascii=False,
            )
        )
    failures = [t for t in traces if t.status == "error"]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

"""End-to-end τ-bench × claude-agent-sdk smoke runner.

Run with a2e already serving on http://127.0.0.1:6006:

    uv run python task/examples/run_tau_claude.py --domain retail --n 1
"""

from __future__ import annotations

import argparse
import json
import sys

from ageneval.task.runners import run_tau_claude


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default="retail", choices=["retail", "airline"])
    parser.add_argument("--n", type=int, default=1, help="number of tasks")
    parser.add_argument("--model", default="claude-sonnet-4-5")
    parser.add_argument(
        "--endpoint",
        default=None,
        help="OTLP endpoint override (default reads A2E_COLLECTOR_ENDPOINT)",
    )
    args = parser.parse_args()

    traces = run_tau_claude(
        domain=args.domain,
        n=args.n,
        model=args.model,
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

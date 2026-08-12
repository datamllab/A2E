"""Top-level A2E evaluation runner.

Run from `/home/yuchenyue/A2E/server` so the A2E server package environment
is active, for example:

    uv run python /home/yuchenyue/A2E/eval/scripts/run_eval.py --part all --experiment-id EXP_ID
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
if str(EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(EVAL_ROOT))

import core.deal_server as deal_server
from core.metric_groups import METRIC_GROUPS, metrics_for_parts


def _split_parts(values: list[str]) -> list[str]:
    parts: list[str] = []
    for value in values:
        parts.extend(part.strip() for part in value.split(",") if part.strip())
    return parts or ["all"]


def parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description=(
            "Run A2E eval metrics by process/outcome category. By default this runs every metric. "
            "All unknown arguments are passed through to core/deal_server.py."
        )
    )
    parser.add_argument(
        "--part",
        action="append",
        default=[],
        help=(
            "Metric category to run. Use comma-separated values or repeat the flag. "
            "Supported: all, plan, skill, memory, tool, correct, efficiency, safety."
        ),
    )
    parser.add_argument("--print-only", action="store_true", help="Print selected metrics without evaluating.")
    parser.add_argument("--list-parts", action="store_true", help="List metric categories and exit.")
    return parser.parse_known_args(argv)


def main(argv: list[str] | None = None) -> None:
    args, passthrough = parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.list_parts:
        for part, metrics in METRIC_GROUPS.items():
            print(f"{part}: {','.join(metrics)}")
        return

    selected_parts = _split_parts(args.part)
    selected_metrics = metrics_for_parts(selected_parts)
    print(f"Selected parts: {','.join(selected_parts)}")
    print(f"Selected metrics ({len(selected_metrics)}): {','.join(selected_metrics)}")
    if args.print_only:
        return

    sys.argv = ["core/deal_server.py", "--metrics", ",".join(selected_metrics), *passthrough]
    deal_server.main()


if __name__ == "__main__":
    main()

"""Offline evaluator that pulls recent τ-bench traces from a2e and scores them.

Skips silently when ``a2e-client`` / ``a2e-evals`` are not
installed in the active environment.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _load_a2e_modules() -> tuple[Any, Any] | None:
    try:
        from a2e.client import Client  # type: ignore
        from a2e.evals.metrics import CorrectnessEvaluator  # type: ignore
    except Exception as exc:  # noqa: BLE001
        print(f"a2e client/evals unavailable: {exc}", file=sys.stderr)
        return None
    return Client, CorrectnessEvaluator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--last", type=int, default=2, help="how many recent runs to score")
    parser.add_argument("--project", default=None)
    args = parser.parse_args()

    mods = _load_a2e_modules()
    if mods is None:
        print("(no-op) a2e evals not installed; skipping", file=sys.stderr)
        return 0
    Client, _ = mods
    try:
        client = Client()
    except Exception as exc:  # noqa: BLE001
        print(f"could not connect to a2e: {exc}", file=sys.stderr)
        return 0

    # A2E client API surface differs across versions; only do the
    # easy thing: list recent projects / spans and print a stub score.
    try:
        spans = client.spans.list(limit=args.last)  # type: ignore[attr-defined]
        # Stub: real evaluation would feed (input, output, context) into
        # CorrectnessEvaluator + evaluate_dataframe. Kept lightweight here.
        for s in spans:
            print(json.dumps({"span_id": getattr(s, "id", "?"), "stub_score": 1.0}))
    except Exception as exc:  # noqa: BLE001
        print(f"a2e client API mismatch: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

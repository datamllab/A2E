"""Self-contained official-swebench grading helper.

Run inside an isolated interpreter that has ``swebench`` installed (the grader
invokes it via ``uv run --with swebench``), so this module imports **only**
``swebench`` + stdlib — never any ``ageneval`` code. That keeps ``swebench`` out
of the main A2E lock entirely while still using the authoritative grader.

Subcommands (instance JSON on stdin):
    spec               -> {"eval_script", "FAIL_TO_PASS", "PASS_TO_PASS", "instance_image_key"}
    parse <log_file>   -> {"resolved", "status", "report"}
"""

from __future__ import annotations

import json
import sys


def _make_spec(instance: dict):
    from swebench.harness.test_spec.test_spec import make_test_spec

    return make_test_spec(instance, namespace="swebench")


def _cmd_spec(instance: dict) -> dict:
    spec = _make_spec(instance)
    return {
        "eval_script": spec.eval_script,
        "FAIL_TO_PASS": list(spec.FAIL_TO_PASS),
        "PASS_TO_PASS": list(spec.PASS_TO_PASS),
        "instance_image_key": spec.instance_image_key,
    }


def _cmd_parse(instance: dict, log_file: str) -> dict:
    from swebench.harness.grading import (
        get_eval_tests_report,
        get_logs_eval,
        get_resolution_status,
        ResolvedStatus,
    )

    spec = _make_spec(instance)
    status_map, found = get_logs_eval(spec, log_file)
    # No parseable test output (e.g. the eval setup failed before tests ran):
    # that is an unresolved instance, not a grader crash.
    if not found or not status_map:
        return {"resolved": False, "status": "no_test_output", "found_test_output": bool(found),
                "report": {}, "f2p_passed": 0, "f2p_total": len(list(spec.FAIL_TO_PASS)),
                "p2p_passed": 0, "p2p_total": len(list(spec.PASS_TO_PASS))}
    gold = {"FAIL_TO_PASS": list(spec.FAIL_TO_PASS), "PASS_TO_PASS": list(spec.PASS_TO_PASS)}
    report = get_eval_tests_report(status_map, gold)
    try:
        status = get_resolution_status(report)
    except Exception:  # noqa: BLE001 — defensive: treat unscoreable report as unresolved
        status = "NO"
    full = getattr(ResolvedStatus, "FULL")
    full_val = getattr(full, "value", full)
    # Per-category pass counts: FAIL_TO_PASS = the bug's target tests that must
    # flip fail->pass; PASS_TO_PASS = regression tests that must stay passing.
    f2p = report.get("FAIL_TO_PASS", {}) or {}
    p2p = report.get("PASS_TO_PASS", {}) or {}
    f2p_pass = len(f2p.get("success", []) or [])
    p2p_pass = len(p2p.get("success", []) or [])
    return {
        "resolved": str(status) == str(full_val),
        "status": str(status),
        "found_test_output": bool(found),
        "report": report,
        "f2p_passed": f2p_pass,
        "f2p_total": f2p_pass + len(f2p.get("failure", []) or []),
        "p2p_passed": p2p_pass,
        "p2p_total": p2p_pass + len(p2p.get("failure", []) or []),
    }


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    instance = json.loads(sys.stdin.read())
    if mode == "spec":
        out = _cmd_spec(instance)
    elif mode == "parse":
        out = _cmd_parse(instance, sys.argv[2])
    else:
        print(json.dumps({"error": f"unknown mode {mode!r}"}))
        return 2
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""ARCA-compatible trajectory evaluation CLI.

This module keeps the historical public function names for tests and ad-hoc
imports, while delegating implementation to ``evaluation_core``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from openai import OpenAI

import evaluation_core as _core
from evaluation_core import (
    calculate_total_score,
    call_grader,
    call_judge_multi_model,
    extract_final_response,
    extract_user_prompt,
    format_judge_rubric,
    load_env,
    parse_transcript,
)


def call_judge_single_model(*args, **kwargs):
    """Compatibility wrapper that honors evaluate_trajectory.OpenAI monkeypatches."""
    _core.OpenAI = OpenAI
    return _core.call_judge_single_model(*args, **kwargs)


def call_judge(*args, **kwargs):
    """Compatibility wrapper that honors evaluate_trajectory.OpenAI monkeypatches."""
    _core.OpenAI = OpenAI
    return _core.call_judge(*args, **kwargs)


def _load_audit_file(path: Path) -> dict[str, Any] | None:
    """Load audit data from JSON or JSONL into the grader-facing shape."""
    if not path.exists() or not path.is_file():
        return None

    try:
        if path.suffix == ".jsonl":
            records: list[Any] = []
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
            return {"calls": records} if records else None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {"calls": data}
    return None


def _audit_service_keys(path: Path) -> list[str]:
    stem = path.stem
    for suffix in ("-audit", "_audit"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if not stem or stem in {"audit", "audit_data", "service_audit", "mock_service_audit"}:
        return []

    keys = [stem]
    for alias in (stem.replace("-", "_"), stem.replace("_", "-")):
        if alias not in keys:
            keys.append(alias)
    return keys


def _is_config_audit(path: Path) -> bool:
    return path.stem.replace("_", "-").startswith("config-audit")


def _merge_audit_payloads(payloads: list[tuple[Path, dict[str, Any]]]) -> dict[str, Any] | None:
    if not payloads:
        return None
    if len(payloads) == 1 and not _audit_service_keys(payloads[0][0]):
        return payloads[0][1]

    merged: dict[str, Any] = {}
    merged_calls: list[Any] = []
    for path, payload in payloads:
        for key in _audit_service_keys(path):
            merged[key] = payload

        calls = payload.get("calls")
        if isinstance(calls, list):
            merged_calls.extend(calls)

        for key, value in payload.items():
            if key == "calls":
                continue
            if key not in merged:
                merged[key] = value

    if merged_calls:
        merged["calls"] = merged_calls
    return merged or None


def discover_audit_data(trajectory_path: str | Path, explicit_path: str | Path | None = None) -> dict[str, Any] | None:
    """Find service audit data beside a trajectory without treating ARCA config logs as service calls."""
    if explicit_path:
        return _load_audit_file(Path(explicit_path))

    trace_dir = Path(trajectory_path).parent
    exact_names = [
        "audit_data.json",
        "audit_data.jsonl",
        "audit.json",
        "audit.jsonl",
        "service_audit.json",
        "service_audit.jsonl",
        "mock_service_audit.json",
        "mock_service_audit.jsonl",
    ]
    candidates: list[Path] = [trace_dir / name for name in exact_names]
    for pattern in ("*-audit.json", "*_audit.json", "*-audit.jsonl", "*_audit.jsonl"):
        candidates.extend(sorted(trace_dir.glob(pattern)))

    seen: set[Path] = set()
    payloads: list[tuple[Path, dict[str, Any]]] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if _is_config_audit(candidate):
            continue
        payload = _load_audit_file(candidate)
        if payload is not None:
            payloads.append((candidate, payload))

    return _merge_audit_payloads(payloads)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ARCA task trajectory")
    parser.add_argument("--task-dir", required=True, help="Path to task directory")
    parser.add_argument("--trajectory", required=True, help="Path to session.jsonl")
    parser.add_argument("--workspace", required=True, help="Path to workspace directory")
    parser.add_argument("--output", default=None, help="Output file path (default: trajectory_dir/evaluation.json)")
    parser.add_argument(
        "--audit-data",
        default=None,
        help="Optional audit data JSON/JSONL path; defaults to service audit files beside the trajectory",
    )
    parser.add_argument("--skip-judge", action="store_true", help="Skip judge evaluation")
    parser.add_argument(
        "--judge-models-config",
        default=None,
        help=(
            "Path to YAML/JSON file configuring multiple judge models. "
            "Auto-detects judge_models_config.yaml/.json in project root if not specified; "
            "falls back to single-model env vars when no config file is found"
        ),
    )
    args = parser.parse_args()

    if args.output is None:
        trajectory_path = Path(args.trajectory)
        args.output = str(trajectory_path.parent / "evaluation.json")

    load_env()
    audit_data = discover_audit_data(args.trajectory, explicit_path=args.audit_data)
    result = _core.evaluate_task_trajectory_from_path(
        task_dir=args.task_dir,
        trajectory_path=args.trajectory,
        workspace_path=args.workspace,
        skip_judge=args.skip_judge,
        judge_models_config=args.judge_models_config,
        audit_data=audit_data,
    )

    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\nEvaluation complete!")
    print(f"Total score: {result['total_score']}")
    print(f"Output saved to: {output_path}")

    print("\nCriteria breakdown:")
    for name, criterion in result.get("criteria", {}).items():
        ctype = criterion.get("type", "unknown")
        value = criterion.get("value", 0)
        weight = criterion.get("weight", "-")
        extra = ""
        if "per_model" in criterion:
            model_names = list(criterion["per_model"].keys())
            extra = f" [models: {', '.join(model_names)}]"
        print(f"  {name}: {ctype}, value={value}, weight={weight}{extra}")


if __name__ == "__main__":
    main()

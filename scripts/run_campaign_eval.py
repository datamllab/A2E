"""Evaluate every experiment recorded by an A2E Campaign.

Run this script with the server Python environment. It launches one
``run_eval.py`` subprocess per Campaign cell and bounds experiment-level
parallelism independently from the per-experiment metric concurrency.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


RUN_EVAL = Path(__file__).resolve().parents[1] / "eval" / "scripts" / "run_eval.py"


@dataclass(frozen=True)
class CampaignExperiment:
    label: str
    experiment_id: str


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _load_experiments(campaign_dir: Path) -> list[CampaignExperiment]:
    lock_path = campaign_dir.expanduser().resolve() / "lock.json"
    if not lock_path.is_file():
        raise ValueError(f"Campaign lock file not found: {lock_path}")

    try:
        lock: dict[str, Any] = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read Campaign lock file: {lock_path}") from exc

    cells = lock.get("cells")
    server_cells = (lock.get("server") or {}).get("cells")
    if not isinstance(cells, list) or not isinstance(server_cells, dict):
        raise ValueError(f"Campaign has no Server experiment state: {lock_path}")

    experiments: list[CampaignExperiment] = []
    seen_ids: set[str] = set()
    missing: list[str] = []
    for index, cell in enumerate(cells, start=1):
        if not isinstance(cell, dict):
            continue
        cell_id = str(cell.get("cell_id") or "")
        harness = str(cell.get("harness") or f"cell-{index}")
        model = str(cell.get("model") or "")
        label = f"{harness}/{model}" if model else harness
        server_cell = server_cells.get(cell_id) or {}
        experiment_id = str(server_cell.get("experiment_id") or "")
        if not experiment_id:
            missing.append(f"{label} ({cell_id or 'unknown cell'})")
            continue
        if experiment_id in seen_ids:
            continue
        seen_ids.add(experiment_id)
        experiments.append(CampaignExperiment(label=label, experiment_id=experiment_id))

    if missing:
        raise ValueError(
            "Campaign cells are missing experiment IDs; run or resume the Campaign first: "
            + ", ".join(missing)
        )
    if not experiments:
        raise ValueError(f"No experiments found in Campaign: {campaign_dir}")
    return experiments


def _parse_args(argv: Sequence[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Run eval/scripts/run_eval.py for every experiment in a Campaign.",
        epilog=(
            "Unknown options are forwarded to run_eval.py, for example: "
            "--part all --base-url http://127.0.0.1:6006 --llm-model gpt-5.6-sol"
        ),
    )
    parser.add_argument(
        "--campaign-dir",
        required=True,
        type=Path,
        help="Campaign run directory containing lock.json.",
    )
    parser.add_argument(
        "--experiment-concurrency",
        type=_positive_int,
        default=2,
        help="Maximum experiments evaluated at once (default: 2).",
    )
    parser.add_argument(
        "--metric-concurrency",
        type=_positive_int,
        default=4,
        help="Concurrency passed to each run_eval.py process (default: 4).",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Print discovered experiments without evaluating them.",
    )
    args, eval_args = parser.parse_known_args(list(argv))
    forbidden = {"--experiment-id", "--concurrency"}
    conflicts = sorted(
        option
        for option in forbidden
        if any(arg == option or arg.startswith(f"{option}=") for arg in eval_args)
    )
    if conflicts:
        parser.error(
            f"{', '.join(conflicts)} is managed by this wrapper; use "
            "--metric-concurrency for per-experiment concurrency"
        )
    return args, eval_args


async def _stream_experiment(
    experiment: CampaignExperiment,
    *,
    semaphore: asyncio.Semaphore,
    metric_concurrency: int,
    eval_args: Sequence[str],
) -> int:
    async with semaphore:
        command = [
            sys.executable,
            str(RUN_EVAL),
            "--experiment-id",
            experiment.experiment_id,
            "--concurrency",
            str(metric_concurrency),
            *eval_args,
        ]
        print(
            f"[{experiment.label}] starting experiment {experiment.experiment_id}",
            flush=True,
        )
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            assert process.stdout is not None
            while line := await process.stdout.readline():
                print(
                    f"[{experiment.label}] {line.decode(errors='replace').rstrip()}",
                    flush=True,
                )
            return_code = await process.wait()
        except asyncio.CancelledError:
            if process.returncode is None:
                process.terminate()
                await process.wait()
            raise
        outcome = "completed" if return_code == 0 else f"failed (exit {return_code})"
        print(f"[{experiment.label}] {outcome}", flush=True)
        return return_code


async def _run_all(
    experiments: Sequence[CampaignExperiment],
    *,
    experiment_concurrency: int,
    metric_concurrency: int,
    eval_args: Sequence[str],
) -> list[int]:
    semaphore = asyncio.Semaphore(experiment_concurrency)
    return list(
        await asyncio.gather(
            *(
                _stream_experiment(
                    experiment,
                    semaphore=semaphore,
                    metric_concurrency=metric_concurrency,
                    eval_args=eval_args,
                )
                for experiment in experiments
            )
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    args, eval_args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        experiments = _load_experiments(args.campaign_dir)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Discovered {len(experiments)} Campaign experiment(s):")
    for experiment in experiments:
        print(f"  {experiment.label}: {experiment.experiment_id}")
    if args.list_only:
        return 0

    try:
        return_codes = asyncio.run(
            _run_all(
                experiments,
                experiment_concurrency=args.experiment_concurrency,
                metric_concurrency=args.metric_concurrency,
                eval_args=eval_args,
            )
        )
    except KeyboardInterrupt:
        print("Interrupted; active eval processes were terminated.", file=sys.stderr)
        return 130

    failed = sum(code != 0 for code in return_codes)
    if failed:
        print(f"Campaign eval finished with {failed}/{len(return_codes)} failure(s).")
        return 1
    print(f"Campaign eval completed for {len(return_codes)} experiment(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

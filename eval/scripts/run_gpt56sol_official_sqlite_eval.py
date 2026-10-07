#!/usr/bin/env python3
"""Offline V2 eval + SQLite writeback for exported official A2E DBs.

Reads experiment_runs/spans from a local SQLite copy, runs AEP evaluators in-process,
and upserts experiment_run_annotations directly (no a2e serve / HTTP API).

Typical layout:
  - Source (read-only): .../zhangmingxuan/gpt-5.6-sol/trajectories/*.db
  - Working copy:       .../yuchenyue/AEP/gpt56sol-eval/gpt56sol-full-writable.db
  - GPFS output:        .../yuchenyue/gpt-5.6-sol-eval/trajectories/*-evaluated.db
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sqlite3
import sys
from collections import defaultdict
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

EVAL_ROOT = Path(__file__).resolve().parents[1]
if str(EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(EVAL_ROOT))

from a2e.evals.executors import SyncExecutor

from core.deal_server import (
    JEV_DIMENSION_METRICS,
    TARGET_METRICS,
    _build_evaluators,
    _with_jev_dimension,
    _create_llm,
    _metrics_require_llm,
    _metrics_require_spans,
    _select_metrics,
)
from core.eval_common import _as_dict, _is_unscored
from core.metric_groups import metrics_for_parts
from core.native_metrics import merge_upstream_eval_annotations
from core.span_store import fetch_spans_by_trace_ids
from process_values.correct_eval import normalize_benchmark_name

LOGGER = logging.getLogger("gpt56sol_sqlite_eval")


def _load_env_file(path: str | None) -> None:
    env_path = path or os.getenv("AEP_EVAL_ENV_FILE") or "/home/yuchenyue/AE2-prep-e2e-latest/.env"
    if not os.path.isfile(env_path):
        return
    for line in Path(env_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
    os.environ.setdefault(
        "OPENAI_API_KEY",
        os.getenv("OPENAI_API_KEY") or os.getenv("AE2_EVAL_LLM_API_KEY") or "",
    )
    os.environ.setdefault(
        "OPENAI_API_BASE",
        os.getenv("OPENAI_API_BASE") or os.getenv("AE2_EVAL_LLM_BASE_URL") or "",
    )
    os.environ.setdefault(
        "A2E_EVAL_LLM_MODEL",
        os.getenv("A2E_EVAL_LLM_MODEL") or os.getenv("AE2_EVAL_LLM_MODEL") or "",
    )


def _ensure_annotation_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS experiment_run_annotations (
            id INTEGER NOT NULL PRIMARY KEY,
            experiment_run_id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            annotator_kind VARCHAR NOT NULL,
            label VARCHAR,
            score FLOAT,
            explanation VARCHAR,
            trace_id VARCHAR,
            error VARCHAR,
            metadata JSONB NOT NULL DEFAULT '{}',
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NOT NULL,
            UNIQUE (experiment_run_id, name)
        )
        """
    )


def _load_experiment(conn: sqlite3.Connection, experiment_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT e.id, e.name, e.dataset_id, e.dataset_version_id, e.metadata
        FROM experiments e WHERE e.id = ?
        """,
        (experiment_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"experiment_id={experiment_id} not found")
    eid, name, dataset_id, dataset_version_id, metadata_raw = row
    metadata = json.loads(metadata_raw) if metadata_raw else {}
    runs = conn.execute(
        """
        SELECT er.id, er.dataset_example_id, er.trace_id, er.output, er.repetition_number,
               der.input, der.output AS expected_output, der.metadata AS example_metadata
        FROM experiment_runs er
        JOIN dataset_example_revisions der ON der.dataset_example_id = er.dataset_example_id
        WHERE er.experiment_id = ?
        ORDER BY er.id
        """,
        (experiment_id,),
    ).fetchall()
    task_runs: list[dict[str, Any]] = []
    for (
        run_id,
        example_id,
        trace_id,
        output_raw,
        repetition_number,
        input_raw,
        expected_raw,
        example_metadata_raw,
    ) in runs:
        task_runs.append(
            {
                "id": str(run_id),
                "dataset_example_id": str(example_id),
                "trace_id": trace_id,
                "output": json.loads(output_raw) if output_raw else {},
                "repetition_number": repetition_number or 1,
                "example": {
                    "id": str(example_id),
                    "input": json.loads(input_raw) if input_raw else {},
                    "output": json.loads(expected_raw) if expected_raw else {},
                    "metadata": json.loads(example_metadata_raw) if example_metadata_raw else {},
                },
            }
        )
    evaluation_runs: list[dict[str, Any]] = []
    for run_id, metric, label, score, explanation in conn.execute(
        """
        SELECT era.experiment_run_id, era.name, era.label, era.score, era.explanation
        FROM experiment_run_annotations era
        JOIN experiment_runs er ON er.id = era.experiment_run_id
        WHERE er.experiment_id = ?
        """,
        (experiment_id,),
    ):
        evaluation_runs.append(
            {
                "experiment_run_id": str(run_id),
                "name": metric,
                "result": {"label": label, "score": score, "explanation": explanation},
            }
        )
    return {
        "experiment_id": base64.b64encode(f"Experiment:{eid}".encode()).decode(),
        "experiment_name": name,
        "dataset_id": str(dataset_id),
        "dataset_version_id": str(dataset_version_id),
        "experiment_metadata": metadata,
        "task_runs": task_runs,
        "evaluation_runs": evaluation_runs,
    }


def _fetch_spans_by_example_id(
    conn: sqlite3.Connection,
    experiment: Mapping[str, Any],
    *,
    limit: int,
) -> dict[str, list[Mapping[str, Any]]]:
    trace_ids = [
        str(run.get("trace_id"))
        for run in experiment.get("task_runs", [])
        if run.get("trace_id")
    ]
    if not trace_ids:
        return {}
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    try:
        spans_by_trace_id = fetch_spans_by_trace_ids(
            trace_ids, limit_per_trace=limit, db_path=db_path
        )
    except sqlite3.OperationalError as exc:
        if "no such table: spans" in str(exc):
            LOGGER.warning("spans table missing in %s; span-backed metrics will use task output only", db_path)
            return {}
        raise
    except sqlite3.DatabaseError as exc:
        LOGGER.warning(
            "span fetch failed in %s (%s); span-backed metrics will use task output only",
            db_path,
            exc,
        )
        return {}
    by_example: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for run in experiment.get("task_runs", []):
        trace_id = str(run.get("trace_id") or "")
        example_id = str(run.get("dataset_example_id") or "")
        if trace_id and example_id:
            by_example[example_id].extend(spans_by_trace_id.get(trace_id, []))
    return dict(by_example)


def _annotator_kind(evaluator: Any) -> str:
    kind = getattr(evaluator, "kind", None) or getattr(evaluator, "annotator_kind", None)
    if kind:
        return str(kind)
    return "CODE"


def _normalize_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return dict(result)
    if isinstance(result, bool):
        return {"score": float(result), "label": "True" if result else "False"}
    if isinstance(result, (int, float)):
        return {"score": float(result)}
    if isinstance(result, str):
        return {"label": result}
    if isinstance(result, tuple) and len(result) == 2:
        score, explanation = result
        return {"score": float(score), "explanation": str(explanation)}
    return {"label": str(result)}


def _upsert_annotation(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    metric_name: str,
    annotator_kind: str,
    result: Mapping[str, Any],
    trace_id: str | None,
    error: str | None,
) -> None:
    now = datetime.now(timezone.utc).isoformat(sep=" ", timespec="microseconds")
    conn.execute(
        """
        INSERT INTO experiment_run_annotations (
            experiment_run_id, name, annotator_kind, label, score, explanation,
            trace_id, error, metadata, start_time, end_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(experiment_run_id, name) DO UPDATE SET
            annotator_kind=excluded.annotator_kind,
            label=excluded.label,
            score=excluded.score,
            explanation=excluded.explanation,
            trace_id=excluded.trace_id,
            error=excluded.error,
            metadata=excluded.metadata,
            start_time=excluded.start_time,
            end_time=excluded.end_time
        """,
        (
            run_id,
            metric_name,
            annotator_kind,
            result.get("label"),
            result.get("score"),
            (str(result.get("explanation") or "")[:1000] if result.get("explanation") else None),
            trace_id,
            error,
            json.dumps(result.get("metadata") or {}),
            now,
            now,
        ),
    )


def _evaluate_experiment_sqlite(
    conn: sqlite3.Connection,
    experiment: Mapping[str, Any],
    evaluators: Mapping[str, Callable[..., dict[str, Any]]],
    *,
    concurrency: int,
    force: bool,
) -> tuple[int, int]:
    completed_by_run: dict[str, set[str]] = defaultdict(set)
    if not force:
        for eval_run in experiment.get("evaluation_runs", []):
            run_id = str(eval_run.get("experiment_run_id") or "")
            name = str(eval_run.get("name") or "")
            result = _as_dict(eval_run.get("result"))
            if run_id and name and not _is_unscored(result) and (
                result.get("score") is not None or bool(str(result.get("label") or ""))
            ):
                completed_by_run[run_id].add(name)

    tasks: list[tuple[int, dict[str, Any], str, Callable[..., dict[str, Any]]]] = []
    for run in experiment.get("task_runs", []):
        run_id = int(run["id"])
        example = run["example"]
        for metric_name, evaluator in evaluators.items():
            if not force and metric_name in completed_by_run.get(str(run_id), set()):
                continue
            tasks.append((run_id, run, metric_name, evaluator))

    if not tasks:
        return 0, 0

    write_lock = Lock()

    def _run_one(item: tuple[int, dict[str, Any], str, Callable[..., dict[str, Any]]]) -> tuple[int, str, dict[str, Any] | None, str | None]:
        run_id, run, metric_name, evaluator = item
        example = run["example"]
        try:
            result = evaluator(
                output=run.get("output") or {},
                expected=example.get("output") or {},
                input=example.get("input") or {},
                example=example,
            )
            return run_id, metric_name, _normalize_result(result), None
        except Exception as exc:
            return run_id, metric_name, None, f"{type(exc).__name__}: {exc}"

    executor = SyncExecutor(
        generation_fn=_run_one,
        max_retries=1,
        exit_on_error=False,
        fallback_return_value=None,
    )
    if concurrency <= 1:
        results, _details = executor.run(tasks)
    else:
        results = []
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(_run_one, task) for task in tasks]
            for future in as_completed(futures):
                results.append(future.result())
    ok = 0
    fail = 0
    for item in results:
        if item is None:
            fail += 1
            continue
        run_id, metric_name, result, error = item
        if result is None:
            fail += 1
            continue
        evaluator = evaluators[metric_name]
        trace_id = next(
            (str(r.get("trace_id")) for r in experiment.get("task_runs", []) if int(r["id"]) == run_id),
            None,
        )
        with write_lock:
            _upsert_annotation(
                conn,
                run_id=run_id,
                metric_name=metric_name,
                annotator_kind=_annotator_kind(evaluator),
                result=result,
                trace_id=trace_id,
                error=error,
            )
        ok += 1
    with write_lock:
        conn.commit()
    return ok, fail


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--experiment-id", help="Base64 Experiment:id or numeric id")
    parser.add_argument("--all-experiments", action="store_true")
    parser.add_argument("--benchmark", default=None)
    parser.add_argument("--part", action="append", default=["all"])
    parser.add_argument("--metrics", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--concurrency", type=int, default=int(os.getenv("AEP_EVAL_CONCURRENCY", "8")))
    parser.add_argument("--span-limit", type=int, default=1000)
    parser.add_argument("--llm-provider", default=os.getenv("A2E_EVAL_LLM_PROVIDER", "openai"))
    parser.add_argument("--llm-model", default=os.getenv("A2E_EVAL_LLM_MODEL", os.getenv("A2E_MODEL", "qwen-max")))
    parser.add_argument("--llm-base-url", default=os.getenv("OPENAI_API_BASE"))
    parser.add_argument("--llm-api-key", default=os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--llm-timeout", type=float, default=120.0)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def _decode_experiment_id(value: str) -> int:
    if value.isdigit():
        return int(value)
    decoded = base64.b64decode(value).decode()
    if decoded.startswith("Experiment:"):
        return int(decoded.split(":", 1)[1])
    raise ValueError(f"Unsupported experiment id: {value}")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    _load_env_file(None)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(message)s")

    metric_names = _with_jev_dimension(
        [m.strip() for m in args.metrics.split(",") if m.strip()]
        if args.metrics
        else list(metrics_for_parts(args.part))
    )
    allowed = set(TARGET_METRICS) | {f"{name}_jev" for name in JEV_DIMENSION_METRICS}
    unknown = sorted(set(metric_names) - allowed)
    if unknown:
        raise ValueError(f"Unsupported metric(s): {unknown}")

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    _ensure_annotation_table(conn)

    if args.all_experiments:
        experiment_ids = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM experiments ORDER BY id"
            ).fetchall()
        ]
    else:
        if not args.experiment_id:
            raise ValueError("Provide --experiment-id or --all-experiments")
        experiment_ids = [_decode_experiment_id(args.experiment_id)]

    deal_args = argparse.Namespace(
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
        llm_base_url=args.llm_base_url,
        llm_api_key=args.llm_api_key,
        llm_timeout=args.llm_timeout,
    )

    total_ok = 0
    total_fail = 0
    for experiment_id in experiment_ids:
        experiment = _load_experiment(conn, experiment_id)
        merge_upstream_eval_annotations(experiment)
        benchmark = args.benchmark or normalize_benchmark_name(experiment.get("experiment_name"))
        selected = _select_metrics(experiment, metric_names, force=args.force)
        if not selected:
            LOGGER.info("skip experiment %s (%s): all metrics present", experiment_id, experiment.get("experiment_name"))
            continue
        if _metrics_require_spans(selected):
            spans_by_example_id = _fetch_spans_by_example_id(
                conn, experiment, limit=args.span_limit
            )
        else:
            spans_by_example_id = {}
            LOGGER.info("skip span fetch: selected metrics do not require spans")
        llm = _create_llm(deal_args) if _metrics_require_llm(selected, benchmark=benchmark) else None
        evaluators = _build_evaluators(
            selected,
            llm=llm,
            spans_by_example_id=spans_by_example_id,
            benchmark=benchmark,
        )
        LOGGER.info(
            "eval experiment_id=%s name=%s runs=%s metrics=%s benchmark=%s",
            experiment_id,
            experiment.get("experiment_name"),
            len(experiment.get("task_runs", [])),
            ",".join(selected),
            benchmark,
        )
        ok, fail = _evaluate_experiment_sqlite(
            conn,
            experiment,
            evaluators,
            concurrency=args.concurrency,
            force=args.force,
        )
        total_ok += ok
        total_fail += fail
        LOGGER.info("done experiment_id=%s ok=%s fail=%s", experiment_id, ok, fail)

    conn.close()
    LOGGER.info("finished db=%s total_ok=%s total_fail=%s", args.db, total_ok, total_fail)
    if total_fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

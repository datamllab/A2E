from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_campaign_eval import _load_experiments, _parse_args  # noqa: E402


def _write_lock(root: Path, data: dict) -> Path:
    root.mkdir()
    (root / "lock.json").write_text(json.dumps(data), encoding="utf-8")
    return root


def test_load_experiments_preserves_campaign_cell_order(tmp_path: Path) -> None:
    campaign = _write_lock(
        tmp_path / "campaign-1",
        {
            "cells": [
                {"cell_id": "cell-agno", "harness": "agno", "model": "model-1"},
                {"cell_id": "cell-lg", "harness": "langgraph", "model": "model-1"},
            ],
            "server": {
                "cells": {
                    "cell-lg": {"experiment_id": "experiment-2"},
                    "cell-agno": {"experiment_id": "experiment-1"},
                }
            },
        },
    )

    experiments = _load_experiments(campaign)

    assert [(item.label, item.experiment_id) for item in experiments] == [
        ("agno/model-1", "experiment-1"),
        ("langgraph/model-1", "experiment-2"),
    ]


def test_load_experiments_rejects_cells_without_server_ids(tmp_path: Path) -> None:
    campaign = _write_lock(
        tmp_path / "campaign-1",
        {
            "cells": [{"cell_id": "cell-agno", "harness": "agno"}],
            "server": {"cells": {}},
        },
    )

    with pytest.raises(ValueError, match="run or resume the Campaign first"):
        _load_experiments(campaign)


def test_parse_args_forwards_eval_options() -> None:
    args, eval_args = _parse_args(
        [
            "--campaign-dir",
            "campaign-1",
            "--experiment-concurrency",
            "3",
            "--metric-concurrency",
            "5",
            "--part",
            "all",
            "--llm-model",
            "gpt-5.6-sol",
        ]
    )

    assert args.campaign_dir == Path("campaign-1")
    assert args.experiment_concurrency == 3
    assert args.metric_concurrency == 5
    assert eval_args == ["--part", "all", "--llm-model", "gpt-5.6-sol"]


def test_parse_args_rejects_wrapper_managed_options() -> None:
    with pytest.raises(SystemExit):
        _parse_args(
            [
                "--campaign-dir",
                "campaign-1",
                "--experiment-id",
                "experiment-1",
            ]
        )

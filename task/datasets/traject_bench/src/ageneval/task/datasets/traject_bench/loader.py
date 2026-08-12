"""traject-bench loader — full set from HuggingFace ``bigboss24/TRAJECT-Bench``.

Schema (per config, e.g. parallel_finance_hard / sequential_travel, split=test):
``query`` (the request), ``tool_list`` (available tools, JSON), ``final_answer``
(reference answer), ``trajectory_type``, ``task_name``, ``task_description``,
``tool_count``. Mapped to: instruction=query, expected_outputs=[final_answer]
(used by ``llm_judge``). Falls back to the vendored sample if HF is unreachable.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from ageneval.task.core.dataset import Dataset, TaskInput
from ageneval.task.datasets.traject_bench._vendor import VENDOR_TASKS

logger = logging.getLogger(__name__)

_HF_ID = "bigboss24/TRAJECT-Bench"

# Published in the dataset card. Keep this fallback so a fully cached run does
# not require a live Hugging Face request just to discover config names.
_CONFIGS = (
    "parallel_education_simple", "parallel_education_hard",
    "parallel_finance_simple", "parallel_finance_hard",
    "parallel_email_simple", "parallel_email_hard",
    "parallel_ecommerce_simple", "parallel_ecommerce_hard",
    "parallel_gaming_simple", "parallel_gaming_hard",
    "parallel_music_simple", "parallel_music_hard",
    "parallel_news_media_simple", "parallel_news_media_hard",
    "parallel_travel_simple", "parallel_travel_hard",
    "parallel_weather_simple", "parallel_weather_hard",
    "sequential_education", "sequential_finance", "sequential_ecommerce",
    "sequential_email", "sequential_gaming", "sequential_mapping",
    "sequential_music", "sequential_news_media", "sequential_travel",
    "sequential_weather",
)


@dataclass
class TrajectBenchDataset(Dataset):
    """Iterable of traject-bench ``TaskInput`` records."""

    name: str
    tasks: Sequence[TaskInput]

    def __iter__(self) -> Iterator[TaskInput]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)


def load_traject_bench_tasks(
    n: int | None = None, split: str = "test", *, hf_id: str | None = _HF_ID, config: str | None = None
) -> TrajectBenchDataset:
    """Load traject-bench (full set across all configs; ``n`` caps)."""
    import os

    # Official TRAJECT-Bench configs expose per-task domain APIs that are not
    # the local 5-tool assistant-utilities executor. Default to the vendored
    # tasks so harness schema tests actually match the bound tools. Set
    # A2E_TRAJECT_HF=1 to force the Hugging Face dump.
    if os.environ.get("A2E_TRAJECT_HF", "0") != "1":
        logger.info("traject-bench: using vendor tasks (set A2E_TRAJECT_HF=1 for HF)")
        return _vendor_dataset(n)
    if hf_id:
        try:
            from datasets import get_dataset_config_names, load_dataset

            if config:
                configs = [config]
            else:
                try:
                    configs = get_dataset_config_names(hf_id)
                except Exception as exc:
                    logger.warning(
                        "traject-bench: config discovery unavailable (%s); "
                        "using the published config list",
                        str(exc)[:80],
                    )
                    configs = list(_CONFIGS)
                if not configs or configs == ["default"]:
                    configs = list(_CONFIGS)
            tasks: list[TaskInput] = []
            hub_failed = False
            for cfg in configs:
                if n is not None and len(tasks) >= n:
                    break
                if hub_failed:
                    break
                try:
                    ds = load_dataset(hf_id, cfg, split=split)
                except Exception as exc:
                    logger.warning(
                        "traject-bench: config %s unavailable (%s); "
                        "stopping HF load and using vendor if needed",
                        cfg,
                        str(exc)[:80],
                    )
                    hub_failed = True
                    continue
                for i, row in enumerate(ds):
                    if n is not None and len(tasks) >= n:
                        break
                    fa = row.get("final_answer")
                    tool_list = row.get("tool_list", "")
                    tasks.append(
                        TaskInput(
                            task_id=f"traject-{cfg}-{i:04d}",
                            instruction=row.get("query") or row.get("instruction") or "",
                            initial_state={"tool_list": tool_list},
                            expected_actions=_expected_actions_from_tool_list(tool_list),
                            expected_outputs=(str(fa),) if fa else (),
                            metadata={"benchmark": "traject-bench", "hf_id": hf_id, "config": cfg,
                                      "trajectory_type": row.get("trajectory_type"), "source": "upstream-full"},
                        )
                    )
            logger.info("traject-bench (hf %s): %d tasks across %d configs", hf_id, len(tasks), len(configs))
            if tasks:
                return TrajectBenchDataset(name="traject-bench", tasks=tasks)
        except Exception as exc:
            logger.warning("traject-bench HF load failed (%s) — falling back to vendor", exc)
    return _vendor_dataset(n)


def _expected_actions_from_tool_list(raw: object) -> tuple[dict, ...]:
    """Turn a TRAJECT-Bench ``tool_list`` field into ``expected_actions``.

    Empty ``expected_actions`` used to make ``tool_recall`` always 1.0.
    """
    data: object = raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return ()
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            data = [part.strip() for part in text.split(",") if part.strip()]
    names: list[str] = []
    if isinstance(data, dict):
        data = data.get("tools") or data.get("tool_list") or list(data)
    if isinstance(data, (list, tuple)):
        for item in data:
            if isinstance(item, str) and item.strip():
                names.append(item.strip())
            elif isinstance(item, dict):
                name = item.get("name") or item.get("tool") or item.get("function")
                if isinstance(name, dict):
                    name = name.get("name")
                if name:
                    names.append(str(name))
    return tuple({"name": n} for n in names)


def _vendor_dataset(n: int | None) -> TrajectBenchDataset:
    raw = VENDOR_TASKS[: (n or len(VENDOR_TASKS))]
    tasks = [
        TaskInput(
            task_id=t["task_id"],
            instruction=t["instruction"],
            initial_state=t.get("initial_state", {}),
            expected_actions=tuple(t.get("expected_actions", ())),
            expected_outputs=tuple(t.get("expected_outputs", ())),
            metadata={"benchmark": "traject-bench", "source": "vendor"},
        )
        for t in raw
    ]
    return TrajectBenchDataset(name="traject-bench-vendor", tasks=tasks)

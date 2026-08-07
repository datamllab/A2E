"""traject-bench loader — full set from HuggingFace ``bigboss24/TRAJECT-Bench``.

Schema (per config, e.g. parallel_finance_hard / sequential_travel, split=test):
``query`` (the request), ``tool_list`` (available tools, JSON), ``final_answer``
(reference answer), ``trajectory_type``, ``task_name``, ``task_description``,
``tool_count``. Mapped to: instruction=query, expected_outputs=[final_answer]
(used by ``llm_judge``). Falls back to the vendored sample if HF is unreachable.
"""

from __future__ import annotations

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
            for cfg in configs:
                if n is not None and len(tasks) >= n:
                    break
                try:
                    ds = load_dataset(hf_id, cfg, split=split)
                except Exception as exc:
                    logger.warning("traject-bench: config %s unavailable (%s); skipping", cfg, str(exc)[:80])
                    continue
                for i, row in enumerate(ds):
                    if n is not None and len(tasks) >= n:
                        break
                    fa = row.get("final_answer")
                    tasks.append(
                        TaskInput(
                            task_id=f"traject-{cfg}-{i:04d}",
                            instruction=row.get("query") or row.get("instruction") or "",
                            initial_state={"tool_list": row.get("tool_list", "")},
                            expected_actions=(),
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

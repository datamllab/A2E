"""PersistBench loader — full set from HuggingFace ``PersistBench/PersistBench``.

Schema (per config beneficial / cross_domain / sycophancy): ``Query`` (the user
request) + ``Memories`` (list of known facts about the user). There is no
ground-truth answer column, so evaluation is via ``llm_judge``; the memories are
folded into the instruction as context. Falls back to the tiny vendored sample
only if HuggingFace is unreachable.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from ageneval.task.core.dataset import Dataset, TaskInput
from ageneval.task.datasets.persistbench._vendor import VENDOR_TASKS

logger = logging.getLogger(__name__)

_HF_ID = "PersistBench/PersistBench"
_DEFAULT_CONFIG = "sycophancy"


@dataclass
class PersistBenchDataset(Dataset):
    name: str
    tasks: Sequence[TaskInput]

    def __iter__(self) -> Iterator[TaskInput]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)


def _fmt_memories(mem) -> str:
    if isinstance(mem, str):
        return mem
    if isinstance(mem, (list, tuple)):
        return "\n".join(f"- {m}" for m in mem)
    return str(mem or "")


def load_persistbench_tasks(
    *, hf_id: str | None = _HF_ID, split: str | None = None, n: int | None = None, config: str | None = None
) -> PersistBenchDataset:
    """Load PersistBench (full set across its three published splits; ``n`` caps)."""
    if hf_id:
        try:
            from datasets import load_dataset

            # Name the published default explicitly. In offline mode the
            # datasets library cannot choose among multiple cached configs.
            dd = load_dataset(hf_id, config or _DEFAULT_CONFIG)
            if hasattr(dd, "items"):
                available_splits = dict(dd.items())
            else:
                available_splits = {split or config or "train": dd}
            if split:
                if split not in available_splits:
                    raise KeyError(
                        f"PersistBench split {split!r} is unavailable; "
                        f"choose one of {sorted(available_splits)}"
                    )
                selected_splits = [(split, available_splits[split])]
            elif config and config in available_splits:
                selected_splits = [(config, available_splits[config])]
            else:
                selected_splits = list(available_splits.items())

            tasks: list[TaskInput] = []
            for split_name, ds in selected_splits:
                if n is not None and len(tasks) >= n:
                    break
                for i, row in enumerate(ds):
                    if n is not None and len(tasks) >= n:
                        break
                    query = row.get("Query") or row.get("query") or row.get("question") or ""
                    mem = _fmt_memories(row.get("Memories"))
                    instruction = query if not mem else f"{query}\n\n[Known memories about the user]\n{mem}"
                    tasks.append(
                        TaskInput(
                            task_id=f"persistbench-{split_name}-{i:04d}",
                            instruction=instruction,
                            expected_outputs=(),
                            metadata={
                                "dataset": "persistbench",
                                "hf_id": hf_id,
                                "split": split_name,
                                "source": "upstream-full",
                            },
                        )
                    )
            logger.info(
                "PersistBench (hf %s): %d tasks across %d splits",
                hf_id,
                len(tasks),
                len(selected_splits),
            )
            if tasks:
                return PersistBenchDataset(name="persistbench", tasks=tasks)
        except Exception as exc:
            logger.warning("PersistBench HF load failed (%s) — falling back to vendor", exc)
    return _load_vendor(n=n)


def _load_vendor(*, n: int | None) -> PersistBenchDataset:
    raw = VENDOR_TASKS[: (n or len(VENDOR_TASKS))]
    tasks = [
        TaskInput(
            task_id=t["task_id"],
            instruction=t["instruction"],
            expected_outputs=tuple(t["expected_outputs"]),
            metadata={"dataset": "persistbench", "source": "vendor"},
        )
        for t in raw
    ]
    return PersistBenchDataset(name="persistbench-vendor", tasks=tasks)

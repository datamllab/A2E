"""DeepSearchQA dataset adapter for A2E."""

from ageneval.task.datasets.deepsearchqa.binding import build_deepsearchqa_binding
from ageneval.task.datasets.deepsearchqa.loader import (
    DeepSearchQADataset,
    load_deepsearchqa_tasks,
)

__all__ = [
    "DeepSearchQADataset",
    "build_deepsearchqa_binding",
    "load_deepsearchqa_tasks",
]

"""MMLU dataset adapter for A2E."""

from ageneval.task.datasets.mmlu.binding import build_mmlu_binding
from ageneval.task.datasets.mmlu.loader import MMLUDataset, load_mmlu_tasks

__all__ = ["MMLUDataset", "build_mmlu_binding", "load_mmlu_tasks"]

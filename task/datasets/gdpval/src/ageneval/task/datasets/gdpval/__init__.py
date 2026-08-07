"""GDPval dataset adapter for A2E."""

from ageneval.task.datasets.gdpval.binding import build_gdpval_binding
from ageneval.task.datasets.gdpval.loader import GDPvalDataset, load_gdpval_tasks

__all__ = [
    "GDPvalDataset",
    "build_gdpval_binding",
    "load_gdpval_tasks",
]

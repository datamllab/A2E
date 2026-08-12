from importlib.metadata import PackageNotFoundError, version

from . import llm, metrics, templating, tracing, utils
from .evaluators import (
    ClassificationEvaluator,
    EvalInput,
    Evaluator,
    KindType,
    LLMEvaluator,
    Score,
    ToolSchema,
    async_evaluate_dataframe,
    bind_evaluator,
    create_classifier,
    create_evaluator,
    evaluate_dataframe,
)
from .llm import LLM, a2e_prompt_to_prompt_template
from .utils import download_benchmark_dataset

try:
    __version__ = version("a2e-evals")
except PackageNotFoundError:
    # PYTHONPATH / source checkout without installed package metadata
    __version__ = "3.0.0"


__all__ = [
    "ClassificationEvaluator",
    "EvalInput",
    "Evaluator",
    "LLMEvaluator",
    "Score",
    "ToolSchema",
    "KindType",
    "create_classifier",
    "create_evaluator",
    "async_evaluate_dataframe",
    "evaluate_dataframe",
    "metrics",
    "templating",
    "llm",
    "LLM",
    "a2e_prompt_to_prompt_template",
    "bind_evaluator",
    "tracing",
    "utils",
    "download_benchmark_dataset",
]

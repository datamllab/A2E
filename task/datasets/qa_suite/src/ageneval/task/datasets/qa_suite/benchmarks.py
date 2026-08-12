"""Config table for HuggingFace-loadable pure-QA benchmarks (no sandbox/skill/memory).

Each row was field-verified against the live HuggingFace dataset on 2026-05-19.
Notes on deviations from the initial design assumptions:

- ``gpqa``: the official ``Idavidrein/gpqa`` is GATED (requires HF auth). Switched
  to the non-gated ``fingertap/GPQA-diamond`` mirror — 198 GPQA-diamond questions
  with the choices already embedded in the ``question`` text and a single-letter
  ``answer`` field (``choices_field`` is ``None``).
- ``bbh``: the originally assumed ``maveriq/bigbenchhard`` is a script-based dataset
  which modern ``datasets`` no longer supports. Switched to ``lukaemon/bbh``
  (parquet, identical content) with split ``test`` instead of ``train``.
- ``agieval``: the originally assumed ``baber/agieval`` is also script-based. Switched
  to ``hails/agieval-aqua-rat`` — question field ``query``, ``choices`` is a list of
  strings already prefixed with ``(A)``…, ``gold`` is a list holding the answer index.
- ``math``: the originally assumed ``lighteval/MATH`` no longer exists / is gated.
  Switched to ``HuggingFaceH4/MATH-500`` which exposes a clean ``answer`` field.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QABenchmark:
    """Static description of one HuggingFace-loadable QA benchmark.

    Attributes:
        key: Short registry name (e.g. ``"arc-challenge"``).
        hf_id: HuggingFace dataset repo id.
        hf_config: HuggingFace dataset config / subset name, or ``None``.
        split: Split to pull (``"test"`` / ``"validation"`` / ``"train"``).
        answer_type: ``"mc"`` (multiple choice), ``"numeric"`` or ``"freeform"``.
        question_field: Row key holding the question text.
        choices_field: Row key holding the answer choices, or ``None`` for
            non-MC benchmarks.
        answer_field: Row key holding the ground-truth answer.
        gated: ``True`` if the dataset requires HuggingFace authentication.
    """

    key: str
    hf_id: str
    hf_config: str | None
    split: str
    answer_type: str
    question_field: str
    choices_field: str | None
    answer_field: str
    gated: bool = False


# Official lukaemon/bbh subset names (27 BIG-Bench Hard tasks).
BBH_CONFIGS: tuple[str, ...] = (
    "boolean_expressions",
    "causal_judgement",
    "date_understanding",
    "disambiguation_qa",
    "dyck_languages",
    "formal_fallacies",
    "geometric_shapes",
    "hyperbaton",
    "logical_deduction_five_objects",
    "logical_deduction_seven_objects",
    "logical_deduction_three_objects",
    "movie_recommendation",
    "multiply",
    "navigate",
    "object_counting",
    "penguins_in_a_table",
    "reasoning_about_colored_objects",
    "ruin_names",
    "salient_translation_error_detection",
    "snarks",
    "sports_understanding",
    "temporal_sequences",
    "tracking_shuffled_objects_five_objects",
    "tracking_shuffled_objects_seven_objects",
    "tracking_shuffled_objects_three_objects",
    "web_of_lies",
    "word_sorting",
)


BENCHMARKS: dict[str, QABenchmark] = {
    # gpqa: official Idavidrein/gpqa is gated -> non-gated fingertap/GPQA-diamond
    # mirror. Choices are embedded in the question text, so choices_field is None.
    "gpqa": QABenchmark(
        "gpqa", "fingertap/GPQA-diamond", "default", "test", "mc",
        "question", None, "answer",
    ),
    "mmlu-pro": QABenchmark(
        "mmlu-pro", "TIGER-Lab/MMLU-Pro", None, "test", "mc",
        "question", "options", "answer",
    ),
    "arc-challenge": QABenchmark(
        "arc-challenge", "allenai/ai2_arc", "ARC-Challenge", "test", "mc",
        "question", "choices", "answerKey",
    ),
    "truthfulqa": QABenchmark(
        "truthfulqa", "truthful_qa", "multiple_choice", "validation", "mc",
        "question", "mc1_targets", "mc1_targets",
    ),
    # bbh: switched maveriq/bigbenchhard (script-based, unsupported) -> lukaemon/bbh.
    # hf_config is the fallback when only one subset is cached. The loader
    # tries every name in BBH_CONFIGS and keeps those present locally.
    "bbh": QABenchmark(
        "bbh", "lukaemon/bbh", "boolean_expressions", "test", "freeform",
        "input", None, "target",
    ),
    # agieval: switched baber/agieval (script-based) -> hails/agieval-aqua-rat.
    "agieval": QABenchmark(
        "agieval", "hails/agieval-aqua-rat", None, "test", "mc",
        "query", "choices", "gold",
    ),
    "commonsenseqa": QABenchmark(
        "commonsenseqa", "tau/commonsense_qa", None, "validation", "mc",
        "question", "choices", "answerKey",
    ),
    "hellaswag": QABenchmark(
        "hellaswag", "Rowan/hellaswag", None, "validation", "mc",
        "ctx", "endings", "label",
    ),
    "openbookqa": QABenchmark(
        "openbookqa", "allenai/openbookqa", "main", "test", "mc",
        "question_stem", "choices", "answerKey",
    ),
    # math: switched lighteval/MATH (removed/gated) -> HuggingFaceH4/MATH-500.
    "math": QABenchmark(
        "math", "HuggingFaceH4/MATH-500", None, "test", "numeric",
        "problem", None, "answer",
    ),
}

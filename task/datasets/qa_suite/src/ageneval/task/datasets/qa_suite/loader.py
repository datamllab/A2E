"""QA Suite loader — config-driven HuggingFace loading for 10 pure-QA benchmarks.

One ``load_qa_tasks`` function handles every benchmark in ``BENCHMARKS`` by
normalizing each row into a ``TaskInput``. Multiple-choice benchmarks expose
heterogeneous choice layouts on HuggingFace (dict ``{text, label}``, plain list,
dict ``{choices, labels}``, list of pre-lettered strings); ``_render_choices``
normalizes them all into an ``A. … / B. …`` block plus a single answer letter.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Iterator, Sequence

from ageneval.task.core.dataset import Dataset, TaskInput

from ageneval.task.datasets.qa_suite.benchmarks import BENCHMARKS, QABenchmark

logger = logging.getLogger(__name__)

_LETTERS = tuple("ABCDEFGHIJKLMNOP")
# strip a leading "(A)" / "A." / "A)" prefix already baked into a choice string
_PREFIX_RE = re.compile(r"^\s*[(\[]?([A-P])[)\].:]\s*")


@dataclass
class QADataset(Dataset):
    """A pure-QA dataset: an iterable of ``TaskInput`` with a name and length."""

    name: str
    tasks: Sequence[TaskInput]

    def __iter__(self) -> Iterator[TaskInput]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)


def _load_hf(hf_id: str, hf_config: str | None, split: str):
    """Load a HuggingFace split, retrying with ``trust_remote_code`` if required."""
    from datasets import load_dataset  # type: ignore

    try:
        return load_dataset(hf_id, hf_config, split=split, streaming=False)
    except Exception as exc:  # noqa: BLE001
        # Older script-based datasets demand trust_remote_code; retry once.
        if "trust_remote_code" in str(exc).lower():
            return load_dataset(
                hf_id, hf_config, split=split, streaming=False, trust_remote_code=True
            )
        raise


def _extract_choices(raw: Any) -> tuple[list[str], list[str] | None]:
    """Return (choice_texts, explicit_labels|None) from a heterogeneous field.

    Handles:
      * dict ``{"text": [...], "label": [...]}`` (ARC, OpenBookQA, CommonsenseQA)
      * dict ``{"choices": [...], "labels": [...]}`` (TruthfulQA mc1_targets)
      * plain ``list`` of strings (MMLU-Pro options, HellaSwag endings, AGIEval)
    """
    if isinstance(raw, dict):
        if "text" in raw:
            return list(raw["text"]), [str(x) for x in raw.get("label", [])] or None
        if "choices" in raw:
            return list(raw["choices"]), None
    if isinstance(raw, (list, tuple)):
        return list(raw), None
    raise ValueError(f"Unrecognized choices field shape: {type(raw)!r}")


def _render_choices(texts: Sequence[str]) -> str:
    """Render choice texts as an ``A. … / B. …`` block, stripping baked-in prefixes."""
    lines = []
    for i, text in enumerate(texts):
        clean = _PREFIX_RE.sub("", str(text)).strip()
        lines.append(f"{_LETTERS[i]}. {clean}")
    return "\n".join(lines)


def _answer_letter(cfg: QABenchmark, row: dict, texts: Sequence[str],
                    labels: list[str] | None) -> str:
    """Resolve the ground-truth answer letter for a multiple-choice row."""
    raw = row.get(cfg.answer_field)

    # TruthfulQA: answer_field == choices_field; correct = first label == 1.
    if cfg.key == "truthfulqa":
        mc = row.get(cfg.answer_field) or {}
        for i, lab in enumerate(mc.get("labels", [])):
            if int(lab) == 1:
                return _LETTERS[i]
        return "?"

    # AGIEval: gold is a list holding the answer index.
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else None
    if raw is None:
        return "?"

    # Already a letter (ARC, OpenBookQA, CommonsenseQA, MMLU-Pro).
    s = str(raw).strip()
    if len(s) == 1 and s.upper() in _LETTERS[: len(texts)]:
        return s.upper()

    # Numeric index (HellaSwag label, AGIEval gold index).
    try:
        idx = int(s)
        if 0 <= idx < len(texts):
            return _LETTERS[idx]
    except (ValueError, TypeError):
        pass

    # Match against explicit labels list, then against choice text.
    if labels and s in labels:
        return _LETTERS[labels.index(s)]
    for i, text in enumerate(texts):
        if str(text).strip() == s:
            return _LETTERS[i]
    return "?"


def load_qa_tasks(
    benchmark: str, n: int | None = 10, split: str | None = None
) -> QADataset:
    """Load a QA benchmark from HuggingFace and convert it to ``TaskInput`` records.

    Args:
        benchmark: Key into ``BENCHMARKS`` (e.g. ``"arc-challenge"``).
        n: Cap on number of examples; ``None`` = full split.
        split: Override the benchmark's default split.

    Returns:
        A ``QADataset`` of normalized ``TaskInput`` records.

    Raises:
        KeyError: Unknown ``benchmark`` key.
        Exception: Any HuggingFace download / gated-access failure is re-raised
            unchanged so the caller (test/eval layer) can skip it.
    """
    cfg = BENCHMARKS[benchmark]
    use_split = split or cfg.split
    ds = _load_hf(cfg.hf_id, cfg.hf_config, use_split)

    tasks: list[TaskInput] = []
    for i, row in enumerate(ds):
        if n is not None and i >= n:
            break

        question = str(row.get(cfg.question_field, ""))

        if cfg.answer_type == "mc" and cfg.choices_field:
            choices_raw = row.get(cfg.choices_field)
            texts, labels = _extract_choices(choices_raw)
            instruction = f"Question: {question}\n{_render_choices(texts)}"
            expected = _answer_letter(cfg, row, texts, labels)
        elif cfg.answer_type == "mc":
            # Choices are already embedded in the question text and the answer
            # field holds the letter directly (e.g. fingertap/GPQA-diamond).
            instruction = f"Question: {question}"
            expected = str(row.get(cfg.answer_field, "")).strip().upper()
        else:
            # numeric / freeform: answer is a plain string/number.
            instruction = question
            expected = str(row.get(cfg.answer_field, "")).strip()

        tasks.append(
            TaskInput(
                task_id=f"{benchmark}-{i}",
                instruction=instruction,
                expected_outputs=(expected,),
                metadata={"answer_type": cfg.answer_type, "benchmark": benchmark},
            )
        )

    logger.info(
        "QA Suite loader: %s (%s/%s), %s tasks",
        benchmark, cfg.hf_id, use_split, len(tasks),
    )
    return QADataset(name=f"qa-{benchmark}", tasks=tasks)

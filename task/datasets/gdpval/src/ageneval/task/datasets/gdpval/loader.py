"""GDPval loader — HuggingFace ``openai/gdpval``.

GDPval (OpenAI) measures model performance on economically valuable, real-world
knowledge-work tasks spanning 44 occupations across 9 GDP sectors. Each row is a
*deliverable-generation* task: a natural-language ``prompt`` (often referencing
attached input files) plus a human-authored grading ``rubric``.

This adapter treats every task as a tool-less generation task (mirroring the
``humaneval`` / ``qa_suite`` no-sandbox style): the agent reads the prompt and
produces the deliverable as free text; an LLM-as-judge then grades that text
against the task's rubric (passed through ``expected_outputs``).

Reference / deliverable *files* are binary office documents (xlsx, pdf, pptx, …)
hosted on the HF hub. A text-only OpenAI-compatible endpoint cannot ingest them,
so the loader does NOT download them; it only surfaces their names in the
instruction so the model can state assumptions about the unseen attachments.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Iterator, Sequence

from ageneval.task.core.dataset import Dataset, TaskInput

logger = logging.getLogger(__name__)

_HF_ID = "openai/gdpval"

# Cap how much rubric text we stash into expected_outputs (the LLM judge hint).
_MAX_RUBRIC_CHARS = 6000


@dataclass
class GDPvalDataset(Dataset):
    """A concrete ``Dataset`` of GDPval deliverable-generation tasks."""

    name: str
    tasks: Sequence[TaskInput]

    def __iter__(self) -> Iterator[TaskInput]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)


def _file_names(raw: object) -> list[str]:
    """Return basenames of a HF ``reference_files`` / ``deliverable_files`` list."""
    out: list[str] = []
    if isinstance(raw, (list, tuple)):
        for item in raw:
            s = str(item)
            out.append(os.path.basename(s.rstrip("/")) or s)
    return out


def _build_instruction(prompt: str, ref_names: list[str]) -> str:
    """Compose the agent instruction from the task prompt + attachment note."""
    instruction = prompt.strip()
    if ref_names:
        listed = "\n".join(f"  - {n}" for n in ref_names)
        instruction += (
            "\n\n[Note] This task references the following attached input file(s) "
            "that are NOT included in this text-only context:\n"
            f"{listed}\n"
            "Proceed by stating any reasonable assumptions about their contents and "
            "produce the most complete, professional deliverable you can."
        )
    return instruction


def load_gdpval_tasks(split: str = "train", n: int | None = 5) -> GDPvalDataset:
    """Download GDPval and convert each task into a ``TaskInput``.

    Args:
        split: HuggingFace split (the public ``openai/gdpval`` exposes ``train``).
        n: Cap on number of tasks; ``None`` = full split.

    Returns:
        A ``GDPvalDataset`` of tool-less deliverable-generation tasks. The grading
        rubric is carried in ``expected_outputs[0]`` so an LLM judge can score the
        produced deliverable against it.

    Raises:
        Exception: HuggingFace download / gated-access failures propagate so the
            caller (test / eval layer) can skip.
    """
    from datasets import load_dataset  # local import: only loading needs HF

    ds = load_dataset(_HF_ID, split=split, streaming=False)
    tasks: list[TaskInput] = []
    for i, row in enumerate(ds):
        if n is not None and i >= n:
            break
        prompt = str(row.get("prompt", "") or "")
        rubric = str(row.get("rubric_pretty", "") or "")[:_MAX_RUBRIC_CHARS]
        ref_names = _file_names(row.get("reference_files"))
        task_id = str(row.get("task_id") or f"gdpval-{i:04d}")
        tasks.append(
            TaskInput(
                task_id=task_id,
                instruction=_build_instruction(prompt, ref_names),
                expected_outputs=(rubric,) if rubric else (),
                metadata={
                    "dataset": "gdpval",
                    "sector": str(row.get("sector", "")),
                    "occupation": str(row.get("occupation", "")),
                    "n_reference_files": len(ref_names),
                },
            )
        )
    logger.info("GDPval loader: %s (%s), %s tasks", _HF_ID, split, len(tasks))
    return GDPvalDataset(name=f"gdpval-{split}", tasks=tasks)

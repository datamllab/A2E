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
from pathlib import Path
from typing import Iterator, Sequence

from ageneval.task.core.dataset import Dataset, TaskInput

logger = logging.getLogger(__name__)

_HF_ID = "openai/gdpval"

# Cap how much rubric text we stash into expected_outputs (the LLM judge hint).
_MAX_RUBRIC_CHARS = 6000
_MAX_ATTACH_CHARS = 12000
_ATTACH_DIR = Path(os.environ.get("A2E_GDPVAL_FILES_DIR", "/root/A2E/.a2e-data-tau-fix/gdpval-files"))


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


def _extract_file_text(path: Path, *, limit: int = _MAX_ATTACH_CHARS) -> str:
    """Best-effort text extraction from an office/text attachment."""
    suffix = path.suffix.lower()
    try:
        if suffix in {".txt", ".md", ".csv", ".tsv", ".json", ".py", ".xml", ".html"}:
            return path.read_text(encoding="utf-8", errors="replace")[:limit]
        if suffix in {".xlsx", ".xlsm", ".xls"}:
            try:
                import openpyxl  # type: ignore
            except ImportError:
                return f"[xlsx present at {path} but openpyxl is not installed]"
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            chunks: list[str] = []
            for sheet in wb.worksheets:
                chunks.append(f"# sheet {sheet.title}")
                for row in sheet.iter_rows(values_only=True):
                    cells = ["" if c is None else str(c) for c in row]
                    if any(cells):
                        chunks.append("\t".join(cells))
                    if sum(len(x) for x in chunks) >= limit:
                        break
            return "\n".join(chunks)[:limit]
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore
            except ImportError:
                return f"[pdf present at {path} but pypdf is not installed]"
            reader = PdfReader(str(path))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
            return text[:limit]
    except Exception as exc:  # noqa: BLE001
        return f"[failed to extract {path.name}: {exc}]"[:200]
    return f"[binary attachment {path.name} ({path.stat().st_size} bytes) saved at {path}]"


def _fetch_reference_file(rel_path: str) -> Path | None:
    """Resolve a GDPval reference file from the local cache or the Hub."""
    rel = str(rel_path).lstrip("/")
    local = _ATTACH_DIR / rel
    if local.is_file():
        return local
    if os.environ.get("A2E_GDPVAL_FILES", "1") == "0":
        return None
    try:
        from huggingface_hub import hf_hub_download  # type: ignore

        path = hf_hub_download(
            repo_id=_HF_ID,
            repo_type="dataset",
            filename=rel,
            local_dir=str(_ATTACH_DIR),
        )
        fetched = Path(path)
        return fetched if fetched.is_file() else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("GDPval attachment %s unavailable (%s)", rel, str(exc)[:160])
        return None


def _build_instruction(prompt: str, ref_names: list[str], excerpts: list[tuple[str, str]]) -> str:
    """Compose the agent instruction from the task prompt + attachments."""
    instruction = prompt.strip()
    if excerpts:
        blocks = []
        for name, text in excerpts:
            blocks.append(f"----- {name} -----\n{text}")
        instruction += (
            "\n\n[Attached input file contents]\n" + "\n\n".join(blocks)
        )
        return instruction
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
        ref_rels = [str(p) for p in (row.get("reference_files") or [])]
        ref_names = _file_names(ref_rels)
        excerpts: list[tuple[str, str]] = []
        local_paths: list[str] = []
        for rel in ref_rels:
            fetched = _fetch_reference_file(rel)
            if fetched is None:
                continue
            local_paths.append(str(fetched))
            excerpts.append((os.path.basename(rel), _extract_file_text(fetched)))
        task_id = str(row.get("task_id") or f"gdpval-{i:04d}")
        tasks.append(
            TaskInput(
                task_id=task_id,
                instruction=_build_instruction(prompt, ref_names, excerpts),
                initial_state={"reference_files": local_paths, "reference_names": ref_names},
                expected_outputs=(rubric,) if rubric else (),
                metadata={
                    "dataset": "gdpval-aa",
                    "sector": str(row.get("sector", "")),
                    "occupation": str(row.get("occupation", "")),
                    "n_reference_files": len(ref_names),
                    "n_attachments_loaded": len(excerpts),
                },
            )
        )
    logger.info("GDPval loader: %s (%s), %s tasks", _HF_ID, split, len(tasks))
    return GDPvalDataset(name=f"gdpval-{split}", tasks=tasks)

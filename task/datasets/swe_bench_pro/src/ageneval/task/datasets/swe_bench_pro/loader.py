"""Load SWE-bench Pro instances into A2E ``TaskInput`` records.

Each HF row becomes a ``TaskInput`` whose ``sandbox`` points at the per-instance
Docker Hub image (``jefzda/sweap-images:{dockerhub_tag}``, working dir ``/app``)
and whose ``metadata`` carries the grading fields the official harness needs
(``base_commit`` / ``before_repo_set_cmd`` / ``selected_test_files_to_run`` /
``fail_to_pass`` / ``pass_to_pass``). The bulky gold ``patch`` / ``test_patch`` /
problem text are intentionally dropped from metadata to keep uploaded examples
small — grading does not need them.

Design rule: this loader must not import ``swebench`` or any harness Python; the
image name comes straight from the dataset's ``dockerhub_tag`` column.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from ageneval.task.core.dataset import Dataset, TaskInput
from ageneval.task.datasets.swe_bench_pro.benchmarks import VARIANTS

logger = logging.getLogger(__name__)

_IMAGE_REPO = "jefzda/sweap-images"  # official SWE-bench Pro Docker Hub repo

_PROBLEM_PROMPT = (
    "Resolve the following GitHub issue by editing the repository source under "
    "/app.\n\n--- ISSUE ---\n{problem}\n--- END ISSUE ---\n"
)

# Fields kept in metadata for the grader (mirrors the official harness inputs).
# Bulky / unused-for-grading fields (patch, test_patch, requirements, interface,
# problem_statement) are deliberately excluded.
_GRADER_FIELDS = (
    "instance_id",
    "repo",
    "repo_language",
    "base_commit",
    "before_repo_set_cmd",
    "selected_test_files_to_run",
    "fail_to_pass",
    "pass_to_pass",
    "dockerhub_tag",
)


def _image_for(dockerhub_tag: str) -> str:
    """Docker Hub image ref for an instance (``jefzda/sweap-images:{tag}``)."""
    return f"{_IMAGE_REPO}:{dockerhub_tag}"


def _maybe_unquote(text: str) -> str:
    """Best-effort decode of a stored string literal.

    SWE-bench Pro stores some text fields (e.g. ``problem_statement``) as a
    quoted/escaped string. Decode it for a readable prompt; fall back to raw.
    """
    s = str(text or "")
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            return json.loads(s)
        except (ValueError, TypeError):
            return s
    return s


def _local_pro_images() -> set[str]:
    """Set of ``jefzda/sweap-images:*`` image refs present locally (best-effort)."""
    import shutil
    import subprocess

    if shutil.which("docker") is None:
        return set()
    try:
        out = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return set()
    return {ln.strip() for ln in out.stdout.splitlines() if ln.strip().startswith(_IMAGE_REPO + ":")}


@dataclass
class SWEBenchProDataset(Dataset):
    """A concrete ``Dataset`` of SWE-bench Pro tasks."""

    name: str
    tasks: Sequence[TaskInput]

    def __iter__(self) -> Iterator[TaskInput]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)


def load_swe_bench_pro_tasks(
    variant: str = "swe-bench-pro",
    n: int | None = 1,
    split: str | None = None,
    instance_ids: Sequence[str] | None = None,
) -> SWEBenchProDataset:
    """Load a SWE-bench Pro variant into ``TaskInput`` records.

    Args:
        variant: One of ``benchmarks.VARIANTS`` (currently ``swe-bench-pro``).
        n: Cap on number of instances when ``instance_ids`` is not given
            (``None`` = full split).
        split: Override the variant's default split.
        instance_ids: If given, load exactly these instance ids (in dataset
            order), ignoring ``n`` — lets a test / demo target an instance whose
            image is already pulled.

    Returns:
        A ``SWEBenchProDataset`` ready to feed ``SandboxScoringRunner``.

    Raises:
        KeyError: unknown ``variant``.
        Exception: HuggingFace download failures propagate so the test layer can
            ``pytest.skip``.
    """
    cfg = VARIANTS[variant]

    from datasets import load_dataset  # local import: only loading needs HF

    ds = load_dataset(cfg.hf_id, split=split or cfg.split)
    wanted = {str(i) for i in instance_ids} if instance_ids else None

    # No explicit pin: prefer instances whose docker image is ALREADY pulled
    # locally so a web/CLI run "just works" without pulling a fresh multi-GB
    # image. Falls back to the first ``n`` instances when nothing is cached.
    if wanted is None and n is not None:
        local_imgs = _local_pro_images()
        if local_imgs:
            cached = [
                str(r["instance_id"])
                for r in ds
                if _image_for(str(r["dockerhub_tag"])) in local_imgs
            ]
            if cached:
                wanted = set(cached[:n])
                logger.info(
                    "SWE-bench Pro loader: %s — preferring %d locally-cached instance(s): %s",
                    variant, len(wanted), sorted(wanted),
                )

    tasks: list[TaskInput] = []
    for row in ds:
        instance_id = str(row["instance_id"])
        if wanted is not None:
            if instance_id not in wanted:
                continue
        elif n is not None and len(tasks) >= n:
            break

        grader_meta = {k: row.get(k) for k in _GRADER_FIELDS}
        image = _image_for(str(row["dockerhub_tag"]))
        tasks.append(
            TaskInput(
                task_id=instance_id,
                instruction=_PROBLEM_PROMPT.format(problem=_maybe_unquote(row.get("problem_statement", ""))),
                initial_state={},
                expected_outputs=(),
                metadata={
                    "variant": variant,
                    "instance_id": instance_id,
                    "repo": row.get("repo", ""),
                    "base_commit": row.get("base_commit", ""),
                    # grader-only view of the row (no bulky gold/test fields)
                    "swebench_pro_instance": grader_meta,
                },
                # SWE-bench Pro images set ENTRYPOINT ["/bin/bash"]; override it
                # with `sleep` so the keepalive process actually runs and the
                # container stays alive for the agent + grader.
                sandbox={
                    "type": "docker",
                    "config": {
                        "image": image,
                        "cwd": "/app",
                        "entrypoint": "sleep",
                        "keepalive": ["infinity"],
                    },
                },
            )
        )
        if wanted is not None and len(tasks) >= len(wanted):
            break

    logger.info("SWE-bench Pro loader: %s (%s), %s tasks", variant, cfg.hf_id, len(tasks))
    return SWEBenchProDataset(name=variant, tasks=tasks)

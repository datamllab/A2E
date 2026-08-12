"""Load SWE-bench instances into A2E ``TaskInput`` records.

Design rule: **this loader must not import ``swebench``**. ``registry.py``
imports loaders eagerly, and ``swebench`` is a heavy/optional dependency — so we
compute the docker image name with a tiny pure helper that mirrors swebench's
naming (verified against ``make_test_spec(...).instance_image_key``). Only the
grader (run lazily, behind the ``grade`` extra) imports ``swebench``.

Each instance becomes a ``TaskInput`` whose ``sandbox`` points at the per-
instance docker image and whose ``metadata`` carries the full HF row so the
grader can build the official test spec.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Iterator, Sequence

from ageneval.task.core.dataset import Dataset, TaskInput

from ageneval.task.datasets.swe_bench.benchmarks import VARIANTS

logger = logging.getLogger(__name__)

_PROBLEM_PROMPT = (
    "Resolve the following GitHub issue by editing the repository source.\n\n"
    "--- ISSUE ---\n{problem}\n--- END ISSUE ---\n"
)

# Fields stored as JSON-encoded strings on the HF hub; parsed to lists.
_JSON_LIST_FIELDS = ("FAIL_TO_PASS", "PASS_TO_PASS")


def _instance_image_key(instance_id: str, arch: str = "x86_64", namespace: str = "swebench") -> str:
    """Docker Hub image name for a SWE-bench instance.

    Mirrors ``swebench.harness.test_spec.TestSpec.instance_image_key``:
    ``{namespace}/sweb.eval.{arch}.{instance_id with __ -> _1776_}:latest``,
    lowercased (docker tags must be lowercase). Verified equal to the official
    value for ``astropy__astropy-12907`` in temp/swebench_api.txt.
    """
    safe_id = instance_id.replace("__", "_1776_")
    return f"{namespace}/sweb.eval.{arch}.{safe_id}:latest".lower()


def _local_swebench_images() -> set[str]:
    """Set of ``swebench/sweb.eval.*`` image tags present locally.

    Best-effort: returns an empty set if the docker CLI is unavailable or errors,
    so callers degrade to the default (first-n) selection.
    """
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
    except Exception:  # noqa: BLE001 - docker missing / daemon down -> no local images
        return set()
    return {
        ln.strip().lower()
        for ln in out.stdout.splitlines()
        if ln.strip().lower().startswith("swebench/sweb.eval.")
    }


def _normalize_instance(row: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of an HF row with JSON-string list fields parsed."""
    inst = dict(row)
    for field_name in _JSON_LIST_FIELDS:
        val = inst.get(field_name)
        if isinstance(val, str):
            try:
                inst[field_name] = json.loads(val)
            except (ValueError, TypeError):
                inst[field_name] = []
    return inst


@dataclass
class SWEBenchDataset(Dataset):
    """A concrete ``Dataset`` of SWE-bench tasks."""

    name: str
    tasks: Sequence[TaskInput]

    def __iter__(self) -> Iterator[TaskInput]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)


def load_swe_bench_tasks(
    variant: str = "swe-bench-lite",
    n: int | None = 1,
    split: str | None = None,
    instance_ids: Sequence[str] | None = None,
) -> SWEBenchDataset:
    """Load a SWE-bench variant into ``TaskInput`` records.

    Args:
        variant: One of ``benchmarks.VARIANTS`` (``swe-bench-lite`` /
            ``swe-bench-verified``).
        n: Cap on number of instances when ``instance_ids`` is not given
            (``None`` = full split).
        split: Override the variant's default split.
        instance_ids: If given, load exactly these instance ids (in dataset
            order), ignoring ``n``. Lets a user / test target specific instances
            (e.g. one whose docker image is already pulled).

    Returns:
        A ``SWEBenchDataset`` ready to feed ``SandboxScoringRunner``.

    Raises:
        KeyError: unknown ``variant``.
        Exception: HuggingFace download / gated-access failures propagate so the
            test layer can ``pytest.skip``.
    """
    cfg = VARIANTS[variant]

    from datasets import load_dataset  # local import: only loading needs HF

    ds = load_dataset(cfg.hf_id, split=split or cfg.split)
    wanted = {str(i) for i in instance_ids} if instance_ids else None

    # No explicit pin: prefer instances whose docker image is ALREADY pulled
    # locally, so a web/CLI run "just works" without hitting Docker Hub's
    # unauthenticated pull rate limit (the per-instance images are multi-GB).
    # Falls back to the first ``n`` instances when nothing is cached locally.
    if wanted is None and n is not None:
        local_imgs = _local_swebench_images()
        if local_imgs:
            cached = [
                str(r["instance_id"])
                for r in ds
                if _instance_image_key(str(r["instance_id"])) in local_imgs
            ]
            if cached:
                wanted = set(cached[:n])
                logger.info(
                    "SWE-bench loader: %s — preferring %d locally-cached instance(s): %s",
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
        inst = _normalize_instance(dict(row))
        image = _instance_image_key(instance_id)
        tasks.append(
            TaskInput(
                task_id=instance_id,
                instruction=_PROBLEM_PROMPT.format(problem=inst.get("problem_statement", "")),
                initial_state={},
                expected_outputs=(),
                metadata={
                    "variant": variant,
                    "instance_id": instance_id,
                    "repo": inst.get("repo", ""),
                    "base_commit": inst.get("base_commit", ""),
                    # full row for the grader (test_patch / FAIL_TO_PASS / version / ...)
                    "swebench_instance": inst,
                },
                sandbox={"type": "docker", "config": {"image": image, "cwd": "/testbed"}},
            )
        )
        if wanted is not None and len(tasks) >= len(wanted):
            break
    logger.info("SWE-bench loader: %s (%s), %s tasks", variant, cfg.hf_id, len(tasks))
    return SWEBenchDataset(name=variant, tasks=tasks)


def setup_swe_bench(task: TaskInput, sandbox) -> None:
    """SandboxScoringRunner setup hook: prepare the environment before the agent.

    Real SWE-bench variants need no setup — the docker image already ships
    ``/testbed`` checked out at ``base_commit``. Kept as a registered hook so the
    runner has a uniform call site.
    """
    return None

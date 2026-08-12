"""Run identity and sampling helpers for isolated A2E experiments."""

from __future__ import annotations

import hashlib
import random
import re
import secrets
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, is_dataclass, replace
from datetime import datetime, timezone
from typing import TypeVar

from ageneval.task.core import TaskInput

DEFAULT_SAMPLE_SIZE = 40

_DatasetT = TypeVar("_DatasetT")
_UNSAFE_NAME_CHARS = re.compile(r"[^a-zA-Z0-9._-]+")
_REPEATED_DASHES = re.compile(r"-+")


@dataclass(frozen=True)
class RunIdentity:
    """Names that bind one CLI invocation to one dataset and experiment."""

    run_id: str
    dataset_name: str
    experiment_name: str
    project_name: str


@dataclass(frozen=True)
class SampleSelection:
    """The exact sample selected for one experiment run."""

    strategy: str
    seed: int | None
    requested_n: int | None
    available_n: int
    selected_n: int
    task_ids: tuple[str, ...]


def _slug(value: object, *, fallback: str) -> str:
    text = _UNSAFE_NAME_CHARS.sub("-", str(value or "").strip())
    text = _REPEATED_DASHES.sub("-", text).strip("-._")
    return text or fallback


def _bounded_name(*parts: object, limit: int = 200) -> str:
    value = "-".join(_slug(part, fallback="unknown") for part in parts)
    if len(value) <= limit:
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{value[: limit - len(digest) - 1].rstrip('-')}-{digest}"


def new_run_id() -> str:
    """Return a sortable run id with enough entropy for concurrent invocations."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def build_run_identity(
    *,
    dataset_name: str,
    dataset_key: str,
    agent_name: str,
    model: str | None,
    run_id: str | None = None,
) -> RunIdentity:
    """Build unique, readable names for one experiment invocation."""
    resolved_run_id = _slug(run_id or new_run_id(), fallback="run")
    model_name = _slug(model, fallback="default-model")
    return RunIdentity(
        run_id=resolved_run_id,
        dataset_name=_bounded_name("a2e", dataset_name, resolved_run_id),
        experiment_name=_bounded_name(
            dataset_key, agent_name, model_name, resolved_run_id
        ),
        project_name=_bounded_name(
            "a2e", dataset_key, agent_name, model_name, resolved_run_id
        ),
    )


def sample_dataset(
    dataset: _DatasetT,
    *,
    n: int | None,
    seed: int | None = None,
) -> tuple[_DatasetT, SampleSelection]:
    """Return a copy of ``dataset`` containing the selected task records.

    ``random`` uses a local PRNG. It never changes process-global random state.
    An omitted seed is generated once and returned in ``SampleSelection`` so the
    exact batch can be replayed later. Selection is always random without
    replacement when ``n`` is provided.
    """
    if n is not None and n <= 0:
        raise ValueError("sample size n must be a positive integer or None")
    if not is_dataclass(dataset) or not hasattr(dataset, "tasks"):
        raise TypeError("registered datasets must be dataclasses with a tasks field")

    available: Sequence[TaskInput] = list(dataset.tasks)  # type: ignore[attr-defined]
    if not available:
        raise ValueError("dataset contains no tasks")
    seen_task_ids: set[str] = set()
    duplicate_task_ids: list[str] = []
    for task in available:
        if task.task_id in seen_task_ids and task.task_id not in duplicate_task_ids:
            duplicate_task_ids.append(task.task_id)
        seen_task_ids.add(task.task_id)
    if duplicate_task_ids:
        preview = ", ".join(repr(task_id) for task_id in duplicate_task_ids[:5])
        raise ValueError(f"dataset contains duplicate task_id values: {preview}")
    if n is not None and n > len(available):
        raise ValueError(
            f"requested {n} cases, but dataset {getattr(dataset, 'name', '<unknown>')!r} "
            f"contains only {len(available)}"
        )

    if n is None:
        selected = list(available)
        effective_strategy = "all"
        effective_seed = None
    else:
        effective_seed = seed if seed is not None else secrets.randbits(63)
        selected = random.Random(effective_seed).sample(list(available), n)
        effective_strategy = "random"

    selected_dataset = replace(dataset, tasks=selected)
    selection = SampleSelection(
        strategy=effective_strategy,
        seed=effective_seed,
        requested_n=n,
        available_n=len(available),
        selected_n=len(selected),
        task_ids=tuple(task.task_id for task in selected),
    )
    return selected_dataset, selection

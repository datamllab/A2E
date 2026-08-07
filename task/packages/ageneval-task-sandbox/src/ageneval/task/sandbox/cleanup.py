"""Leak-sweep for A2E sandbox containers.

The per-task lifecycle already removes its own container (``--rm`` plus the
``sandbox_session`` finally calling ``cleanup()``). This module is the
*belt-and-suspenders* backstop for the one case those cannot cover: a run that
is hard-killed (SIGKILL / pod restart / job timeout) before its finally runs,
leaving an orphan container alive. Accumulated orphans waste RAM/disk and
muddy ``docker ps`` for the next CLI or web run.

``sweep_sandbox_containers`` force-removes only containers that A2E provably
created — matched by our ``a2e.sandbox=1`` label (containers started after the
label was introduced) plus, as a migration aid, any container whose image name
starts with an A2E sandbox image prefix (``swebench/sweb.eval.`` — these images
are only ever started by A2E's SWE-bench grading, never by a human session).
It never touches unrelated containers and never raises.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Sequence

from ageneval.task.sandbox.docker import A2E_SANDBOX_LABEL

logger = logging.getLogger(__name__)

# Image-name prefixes that are exclusively produced by A2E sandbox datasets.
# Used to reclaim legacy orphans created before the label existed.
_A2E_IMAGE_PREFIXES: tuple[str, ...] = ("swebench/sweb.eval.", "swebench/sweb.base.")


def _run(cmd: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Run a docker CLI command, capturing output; never raise on nonzero."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _docker_available() -> bool:
    try:
        return _run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=20).returncode == 0
    except Exception:
        return False


def _labeled_container_ids() -> set[str]:
    label_key = A2E_SANDBOX_LABEL.split("=", 1)[0]
    res = _run(["docker", "ps", "-aq", "--filter", f"label={label_key}"], timeout=30)
    return {cid for cid in res.stdout.split() if cid}


def _image_orphan_ids(prefixes: Sequence[str]) -> set[str]:
    """Container ids whose image name starts with an A2E-only prefix."""
    res = _run(
        ["docker", "ps", "-a", "--no-trunc", "--format", "{{.ID}}\t{{.Image}}"],
        timeout=30,
    )
    ids: set[str] = set()
    for line in res.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        cid, image = parts[0].strip(), parts[1].strip()
        if cid and any(image.startswith(p) for p in prefixes):
            ids.add(cid)
    return ids


def sweep_sandbox_containers(
    *,
    include_image_orphans: bool = True,
    image_prefixes: Sequence[str] = _A2E_IMAGE_PREFIXES,
) -> list[str]:
    """Force-remove leftover A2E sandbox containers; return removed ids.

    Args:
        include_image_orphans: also remove containers whose image name matches an
            A2E-only prefix even if they lack the label (legacy orphans).
        image_prefixes: image-name prefixes treated as A2E-only.

    Safe to call when docker is absent (returns ``[]``) and idempotent.
    """
    if not _docker_available():
        return []
    try:
        targets = _labeled_container_ids()
        if include_image_orphans:
            targets |= _image_orphan_ids(image_prefixes)
    except Exception as exc:
        logger.warning("sandbox sweep: could not list containers: %s", exc)
        return []
    if not targets:
        return []
    removed: list[str] = []
    for cid in targets:
        try:
            if _run(["docker", "rm", "-f", cid], timeout=60).returncode == 0:
                removed.append(cid)
        except Exception as exc:
            logger.warning("sandbox sweep: failed to remove %s: %s", cid[:12], exc)
    if removed:
        logger.info("sandbox sweep: removed %d leftover container(s): %s",
                    len(removed), ", ".join(c[:12] for c in removed))
    return removed


__all__ = ["A2E_SANDBOX_LABEL", "sweep_sandbox_containers"]

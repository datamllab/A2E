"""Build cached task images containing a complete Node.js coding harness."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

from ageneval.task.sandbox.spec import SandboxSpec

_SAFE_IMAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@:+-]*$")
_SAFE_KIND = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_IGNORED_PARTS = {".git", "dist", "node_modules", "test-dist", "__pycache__"}
_BUILD_FORMAT_VERSION = "2"


class HarnessImageError(RuntimeError):
    """Raised when a containerized harness image cannot be prepared."""


def _source_digest(
    package_dir: Path,
    *,
    base_image: str,
    builder_image: str,
    kind: str,
    setup: str,
    rebuild_packages: Sequence[str],
) -> str:
    digest = hashlib.sha256()
    digest.update(
        (
            f"{_BUILD_FORMAT_VERSION}\0{base_image}\0{builder_image}\0{kind}\0{setup}\0"
            f"{' '.join(rebuild_packages)}\0"
        ).encode()
    )
    for path in sorted(package_dir.rglob("*")):
        if not path.is_file() or any(part in _IGNORED_PARTS for part in path.parts):
            continue
        relative = path.relative_to(package_dir).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def _run(command: list[str], *, cwd: Path, input: str | None = None) -> str:
    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            input=input,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3600,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise HarnessImageError(f"failed to run {' '.join(command)}: {exc}") from exc
    if process.returncode != 0:
        detail = (process.stderr or process.stdout)[-4000:]
        raise HarnessImageError(f"{' '.join(command)} failed:\n{detail}")
    return process.stdout.strip()


def prepare_node_harness_image(
    spec: SandboxSpec,
    *,
    package_dir: str | os.PathLike[str],
    kind: str,
    setup_command: str = "",
    rebuild_packages: Sequence[str] = (),
) -> SandboxSpec:
    """Return a Docker spec whose image contains the supplied harness package.

    The build is content-addressed and cached by Docker. ``npm ci`` and the
    TypeScript build happen in Linux, so Windows host ``node_modules`` are
    never copied into benchmark containers.
    """

    if spec.type != "docker":
        return spec
    base_image = str(spec.config.get("image") or "")
    if not _SAFE_IMAGE.fullmatch(base_image):
        raise HarnessImageError(f"unsafe or missing Docker image name: {base_image!r}")
    if not _SAFE_KIND.fullmatch(kind):
        raise HarnessImageError(f"unsafe harness kind: {kind!r}")
    if any(not _SAFE_KIND.fullmatch(package) for package in rebuild_packages):
        raise HarnessImageError(f"unsafe npm rebuild package list: {rebuild_packages!r}")
    builder_image = os.environ.get("A2E_HARNESS_NODE_IMAGE", "node:22-bullseye-slim")
    if not _SAFE_IMAGE.fullmatch(builder_image):
        raise HarnessImageError(f"unsafe Node builder image name: {builder_image!r}")
    source = Path(package_dir).resolve()
    if not (source / "package.json").is_file() or not (source / "package-lock.json").is_file():
        raise HarnessImageError(f"harness package is incomplete: {source}")

    digest = _source_digest(
        source,
        base_image=base_image,
        builder_image=builder_image,
        kind=kind,
        setup=setup_command,
        rebuild_packages=rebuild_packages,
    )
    image = f"a2e-local/{kind}-harness:{digest}"
    inspected = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if inspected.returncode != 0:
        setup = f"RUN {setup_command}\n" if setup_command else ""
        rebuild = (
            f"RUN npm rebuild {' '.join(rebuild_packages)}\n" if rebuild_packages else ""
        )
        dockerfile = (
            f"FROM {builder_image} AS a2e-harness-build\n"
            "WORKDIR /opt/a2e-harness\n"
            "COPY package.json package-lock.json ./\n"
            "RUN npm ci --ignore-scripts\n"
            f"{rebuild}"
            "COPY . .\n"
            "RUN npm run build\n"
            "RUN mkdir -p /opt/a2e-dsh\n"
            f"{setup}"
            f"FROM {base_image}\n"
            "COPY --from=a2e-harness-build /usr/local/bin/node /usr/local/bin/node\n"
            "COPY --from=a2e-harness-build /opt/a2e-harness /opt/a2e-harness\n"
            "COPY --from=a2e-harness-build /opt/a2e-dsh /opt/a2e-dsh\n"
        )
        _run(
            ["docker", "build", "--pull=false", "--tag", image, "--file", "-", "."],
            cwd=source,
            input=dockerfile,
        )

    config = dict(spec.config)
    config["image"] = image
    config["pull"] = False
    return SandboxSpec(type=spec.type, config=config)
